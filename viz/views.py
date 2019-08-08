import flask
import flask_classful as flaskc
import os
import itertools as it
import json
from viz import shared
from multiprocessing import Process
from multiprocessing.pool import Pool as mpp
import threading
from datetime import datetime as dt
import time
import sys

def getModel(sm, s, result):
    projectID, response, templates = sm.searchTemplates(s)
    templates.sort(key=lambda t: float(t["comment"]["prob"]) if "prob" in t["comment"] else 0.0)
    result["getmodel_" + s] = sm.buildModel(projectID, templates[0]["id"])

def extractFragments(sequence, n):
    fragments = []
    for i in range(0, len(sequence) - n):
        s = slice(i, i+n)
        if sequence[s] not in fragments:
            fragments.append(sequence[s])
    return fragments

def compareSequenceToFragment(sequence, fragment):
    return (sequence.find(fragment) > -1)

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
    
    @flaskc.route("/sequence/fragment/list", methods=["GET"])
    def sequence_fragment_list(self):
        return flask.jsonify(self.sharedVars.sequenceFragments)

    @flaskc.route("/sequence/add", methods=["POST"])
    def sequence_add(self):
        requestForm = flask.request.get_json()
        if "sequence" in requestForm and "sequenceName" in requestForm:
            timestamp = str(dt.utcnow().timestamp())
            self.sharedVars.sequences[requestForm["sequenceName"]] = requestForm["sequence"]
            self.sharedVars.tasks["sequence-add-" + timestamp] = {
                "type" : "sequence-add",
                "startTime" : timestamp,
                "sequenceName" : requestForm["sequenceName"],
                "status" : "running"
            }
            def taskThread(sharedVars):
                taskResults = sharedVars.taskResults.dict()
                getModelProcess = Process(target=getModel, args=(sharedVars.swissmodel, sharedVars.sequences[requestForm["sequenceName"]], taskResults))
                getModelProcess.daemon = True
                getModelProcess.start()
                while getModelProcess.is_alive():
                    time.sleep(1)
                sharedVars.tasks["sequence-add-" + timestamp]["status"] = "completed"
                sharedVars.saveModel(taskResults["getmodel_" + sharedVars.sequences[requestForm["sequenceName"]]], requestForm["sequenceName"])

            th = threading.Thread(target=taskThread, args=(self.sharedVars,))
            th.daemon = True
            th.start()
            return flask.jsonify(self.sharedVars.tasks["sequence-add-" + timestamp])
        return flask.abort(405)

    @flaskc.route("/sequence/compare", methods=["POST"])
    def sequence_compare(self):
        requestForm = flask.request.get_json()
        if "sequenceNames" in requestForm:
            timestamp = str(dt.utcnow().timestamp())
            self.sharedVars.tasks["sequence-compare-" + timestamp] = {
                "type" : "sequence-compare",
                "startTime" : timestamp,
                "sequenceNames" : requestForm["sequenceNames"],
                "status" : "running",
                "messages" : []
            }
            def taskThread(sharedVars):
                fragments = []
                for sequenceName in requestForm["sequenceNames"]:
                    if sequenceName in sharedVars.sequences:
                        sharedVars.tasks["sequence-compare-" + timestamp]["messages"].append("Computing fragments for " + sequenceName)
                        sequence = sharedVars.sequences[sequenceName]
                        pool = mpp(sharedVars.nworkers)
                        f = pool.starmap(extractFragments, zip(it.repeat(sequence), range(30, len(sequence))))
                        pool.close()
                        pool.join()
                        del pool
                        fragments.append(list(set().union(*f)))
                
                fragments = list(set().union(*fragments))

                pool = mpp(sharedVars.nworkers)
                sequenceResults = {}
                for sequenceName in requestForm["sequenceNames"]:
                    if sequenceName in sharedVars.sequences:
                        sharedVars.tasks["sequence-compare-" + timestamp]["messages"].append("Finding fragment occurences in " + sequenceName)
                        sequence = sharedVars.sequences[sequenceName] 
                        taskResults = pool.starmap(compareSequenceToFragment, zip(it.repeat(sequence), fragments))
                        sequenceResults[sequenceName] = taskResults
                pool.close()
                pool.join()
                del pool
                
                fragmentCount = {}
                for sequenceName in sequenceResults:
                    sharedVars.tasks["sequence-compare-" + timestamp]["messages"].append("Cleaning fragment results for " + sequenceName)
                    for i in range(len(fragments)):
                        if sequenceResults[sequenceName][i]:
                            if fragments[i] in fragmentCount:
                                fragmentCount[fragments[i]] += 1
                            else:
                                fragmentCount[fragments[i]] = 1

                for fragment in fragments:
                    if fragmentCount[fragment] <= 1:
                        fragmentCount.pop(fragment)

                validFragments = list(fragmentCount.keys())
                sharedVars.tasks["sequence-compare-" + timestamp]["messages"].append("Checking for maximal containment between fragments")
                print(len(validFragments))
                for fragment_a in validFragments:
                    if fragment_a in fragmentCount:
                        for fragment_b in validFragments:
                            if fragment_b in fragmentCount:
                                if fragment_a in fragmentCount and fragment_b in fragmentCount:
                                    if len(fragment_b) < len(fragment_a) and (fragment_a.find(fragment_b) > -1):
                                        if fragmentCount[fragment_a] == fragmentCount[fragment_b]:
                                            fragmentCount.pop(fragment_b)
                                        else:
                                            splitfrag = fragment_a.split(fragment_b)
                                            for sf in splitfrag:
                                                if len(sf) > 29:
                                                    fragmentCount[sf] = fragmentCount[fragment_a]
                                            fragmentCount.pop(fragment_a)
                
                sharedVars.tasks["sequence-compare-" + timestamp]["messages"].append("Adding shared sequence fragments to database")
                fragmentIndex = len(sharedVars.sequenceFragments)
                for fragment in fragmentCount:
                    sequenceFragmentName = "fragment_" + str(fragmentIndex)
                    t = str(dt.utcnow().timestamp())
                    sharedVars.sequenceFragments[sequenceFragmentName] = fragment
                    sharedVars.tasks["sequence-fragment-add-" + t] = {
                        "type" : "sequence-fragment-add",
                        "startTime" : t,
                        "sequenceFragmentName" : sequenceFragmentName,
                        "status" : "running",
                        "result" : None
                    }
                    def fragmentAddThread(sv, tm, sn):
                        taskResults = sv.taskResults.dict()
                        getModelProcess = Process(target=getModel, args=(sv.swissmodel, sv.sequenceFragments[sn], taskResults))
                        getModelProcess.daemon = True
                        getModelProcess.start()
                        while getModelProcess.is_alive():
                            time.sleep(1)
                        sv.tasks["sequence-fragment-add-" + tm]["status"] = "completed"
                        sv.saveModel(taskResults["getmodel_" + sv.sequenceFragments[sn]], sn)

                    th = threading.Thread(target=fragmentAddThread, args=(sharedVars, t, sequenceFragmentName))
                    th.daemon = True
                    th.start()
                    fragmentIndex += 1
                
                sharedVars.tasks["sequence-compare-" + timestamp]["status"] = "completed"
 
            th = threading.Thread(target=taskThread, args=(self.sharedVars,))
            th.daemon = True
            th.start()
            return flask.jsonify(self.sharedVars.tasks["sequence-compare-" + timestamp])
        return flask.abort(405)

    @flaskc.route("/sequence/pdb", methods=["POST"])
    def sequence_pdb(self):
        requestForm = flask.request.get_json()
        if "sequenceName" in requestForm and requestForm["sequenceName"] in self.sharedVars.sequences:
            pdbPath = os.path.join(self.sharedVars.outputPath, requestForm["sequenceName"] + "/model/01/model.pdb")
            if os.path.exists(pdbPath):
                return flask.send_file(pdbPath, attachment_filename='model.pdb', mimetype="chemical/x-pdb")
        return flask.abort(404)

    @flaskc.route("/sequence/graph", methods=["GET"])
    def sequence_graph(self):
        nodes = []
        links = []
        for sequenceName in self.sharedVars.sequences:
            splitSequence = [self.sharedVars.sequences[sequenceName]]
            for f in self.sharedVars.sequenceFragments.values():
                sscopy = splitSequence[:]
                for s in sscopy:
                    if len(s) > len(f):
                        i = splitSequence.index(s)
                        ssplit = s.split(f)
                        if len(ssplit) > 1:
                            del splitSequence[i]
                            j = 0
                            for ss in ssplit:
                                if len(ss) > 0:
                                    splitSequence.insert(i + j, ss)
                                    splitSequence.insert(i + j + 1, f)
                                    j += 2
                                else:
                                    splitSequence.insert(i + j, f)
                                    j += 1
            for i in range(1, len(splitSequence)):
                if splitSequence[i - 1] not in nodes:
                    nodes.append(splitSequence[i - 1])
                if splitSequence[i] not in nodes:
                    nodes.append(splitSequence[i])
                source = nodes.index(splitSequence[i - 1])
                target = nodes.index(splitSequence[i])
                links.append({"source" : source, "target": target, "group": sequenceName})
        return flask.jsonify({"nodes": [{"id" : i, "sequence": nodes[i], "type": ("residue" if nodes[i] not in self.sharedVars.sequenceFragments.values() else "fragment")} for i in range(len(nodes))], "links": links})
        
    @flaskc.route("/sequence/fragment/add", methods=["GET"])
    def sequence_fragment_add(self):
        requestForm = flask.request.get_json()
        if "sequenceFragment" in requestForm and "sequenceFragmentName" in requestForm:
            
            return flask.jsonify(self.sharedVars.tasks["sequence-fragment-add-" + timestamp] )

    @flaskc.route("/task/list", methods=["GET"])
    def task_list(self):
        return flask.jsonify(self.sharedVars.tasks)

    @flaskc.route("/task/get", methods=["POST"])
    def task_get(self):
        requestForm = flask.request.get_json()
        if "type" in requestForm and "startTime" in requestForm and (requestForm["type"] + "-" + requestForm["startTime"]) in self.sharedVars.tasks:
            return flask.jsonify(self.sharedVars.tasks[requestForm["type"] + "-" + requestForm["startTime"]])
        return flask.abort(405)

def initializeViews(workingDIR):
    app = flask.Flask("Viz", template_folder=os.path.join(workingDIR, "viz/templates"), static_folder=os.path.join(workingDIR, "viz/static"))
    variables = shared.Shared(app, os.path.join(workingDIR, "output/"), os.path.join(workingDIR, "data/config.json"))
    MainView.register(app, init_argument=variables)
    BackendView.register(app, init_argument=variables)
    app.run(host="0.0.0.0", port="1337", debug=True)