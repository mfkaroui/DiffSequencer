import flask
import flask_classful as flaskc
import os
import json
from viz import shared

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

class BackendView(flaskc.FlaskView):
    route_base = "/backend/"

    def __init__(self, sharedVars):
        self.sharedVars = sharedVars

    @flaskc.route("/hardwareStats", methods=["GET"])
    def hardwareStats(self):
        return flask.jsonify(self.sharedVars.getHardwareStats())

    @flaskc.route("/outgoingRequests", methods=["GET"])
    def outgoingRequests(self):
        return flask.jsonify(self.sharedVars.requests)

    @flaskc.route("/sequence/validate", methods=["POST"])
    def sequence_validate(self):
        try:
            requestForm = flask.request.get_json()
            if "sequence" in requestForm:
                self.sharedVars.requests.append({
                    "Type" : "Sequence Validate",
                    "Source" : "SwissModel",
                    "Data" : {
                        "Sequence" : requestForm["sequence"]
                    }
                })
                result = self.sm.validateSequence(requestForm["sequence"])
                if result is not None:
                    return flask.jsonify(result)
                else:
                    return flask.abort(404)
        except:
            return flask.abort(404)
    
    @flaskc.route("/sequence/list", methods=["GET"])
    def sequence_list(self):
        return flask.jsonify(self.sharedVars.sequences)
    
    @flaskc.route("/sequence/fragement/list", methods=["GET"])
    def sequence_fragement_list(self):
        return flask.jsonify(self.sharedVars.sequenceFragments)

def initializeViews(workingDIR):
    app = flask.Flask("Viz", template_folder=os.path.join(workingDIR, "viz/templates"), static_folder=os.path.join(workingDIR, "viz/static"))
    variables = shared.Shared(app, os.path.join(workingDIR, "data/config.json"))
    MainView.register(app, init_argument=variables)
    BackendView.register(app, init_argument=variables)
    app.run(host="0.0.0.0", port="1337", debug=True)