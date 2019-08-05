import flask
import flask_classful as flaskc
import os
import json
from viz import shared
from multiprocessing import Process
import threading
from datetime import datetime as dt
import time
import sys

def getModel(sm, s, result):
    projectID, response, templates = sm.searchTemplates(s)
    templates.sort(key=lambda t: float(t["comment"]["prob"]) if "prob" in t["comment"] else 0.0)
    result["getmodel_" + s] = sm.buildModel(projectID, templates[0]["id"])

class MainView(flaskc.FlaskView):
    route_base = "/"

    def __init__(self, sharedVars):
        self.sharedVars = sharedVars

    @flaskc.route("/", methods=["GET"])
    @flaskc.route("/dashboard", methods=["GET"])
    def dashboard(self):
        return flask.render_template("dashboard/index.html")

    @flaskc.route("/sequences", methods=["GET"])
    def sequences(self):
        return flask.render_template("sequences/index.html")
    
    @flaskc.route("/similarity_network", methods=["GET"])
    def similarity_network(self):
        return flask.render_template("similarity_network/index.html")

    @flaskc.route("/model_viewer", methods=["GET"])
    def model_viewer(self):
        return flask.render_template("model_viewer/index.html")

class BackendView(flaskc.FlaskView):
    route_base = "/backend/"

    def __init__(self, sharedVars):
        self.sharedVars = sharedVars

    @flaskc.route("/hardwareStats", methods=["GET"])
    def hardwareStats(self):
        return flask.jsonify(self.sharedVars.getHardwareStats())

    @flaskc.route("/sequence/validate", methods=["POST"])
    def sequence_validate(self):
        try:
            requestForm = flask.request.get_json()
            if "sequence" in requestForm:
                requestForm["sequence"] = requestForm["sequence"].replace("\n", "")
                result = self.sharedVars.swissmodel.validateSequence(requestForm["sequence"])
                if result is not None:
                    return flask.jsonify(result)
                else:
                    return flask.abort(404)
        except:
            return flask.abort(405)

    @flaskc.route("/sequence/list", methods=["GET"])
    def sequence_list(self):
        return flask.jsonify(self.sharedVars.sequences)
    
    @flaskc.route("/sequence/fragement/list", methods=["GET"])
    def sequence_fragement_list(self):
        return flask.jsonify(self.sharedVars.sequenceFragments)

    @flaskc.route("/sequence/add", methods=["POST"])
    def sequence_add(self):
        requestForm = flask.request.get_json()
        if "sequence" in requestForm and "sequenceName" in requestForm:
            timestamp = str(int(dt.utcnow().timestamp()))
            self.sharedVars.sequences[requestForm["sequenceName"]] = requestForm["sequence"]
            self.sharedVars.tasks["sequence-add-" + timestamp] = {
                "type" : "sequence-add",
                "startTime" : timestamp,
                "sequenceName" : requestForm["sequenceName"],
                "status" : "running"
            }
            def taskThread(sharedVars):
                taskResults = sharedVars.taskResults.dict()
                getModelProcess = Process(target=getModel, args=(sharedVars.swissmodel, self.sharedVars.sequences[requestForm["sequenceName"]], taskResults))
                getModelProcess.daemon = True
                getModelProcess.start()
                while getModelProcess.is_alive():
                    time.sleep(1)
                sharedVars.tasks["sequence-add-" + timestamp]["status"] = "completed"
                sharedVars.saveModel(taskResults["getmodel_" + sharedVars.sequences[requestForm["sequenceName"]]], requestForm["sequenceName"])

            th = threading.Thread(target=taskThread, args=(self.sharedVars,))
            th.daemon = True
            th.start()
            return flask.jsonify(self.sharedVars.tasks["sequence-add-" + timestamp] )

    @flaskc.route("/sequence/pdb", methods=["POST"])
    def sequence_pdb(self):
        requestForm = flask.request.get_json()
        if "sequenceName" in requestForm and requestForm["sequenceName"] in self.sharedVars.sequences:
            pdbPath = os.path.join(self.sharedVars.outputPath, requestForm["sequenceName"] + "/model/01/model.pdb")
            if os.path.exists(pdbPath):
                return flask.send_file(pdbPath, attachment_filename='model.pdb', mimetype="chemical/x-pdb")
        return flask.abort(404)

def initializeViews(workingDIR):
    app = flask.Flask("Viz", template_folder=os.path.join(workingDIR, "viz/templates"), static_folder=os.path.join(workingDIR, "viz/static"))
    variables = shared.Shared(app, os.path.join(workingDIR, "output/"), os.path.join(workingDIR, "data/config.json"))
    MainView.register(app, init_argument=variables)
    BackendView.register(app, init_argument=variables)
    app.run(host="0.0.0.0", port="1337", debug=True)