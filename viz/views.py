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
                result = self.sm.validateSequence(requestForm["sequence"])
                if result is not None:
                    return flask.jsonify(result)
                else:
                    return flask.abort(404)
        except:
            return flask.abort(404)
    
    

def initializeViews(workingDIR):
    app = flask.Flask("Viz", template_folder=os.path.join(workingDIR, "viz/templates"), static_folder=os.path.join(workingDIR, "viz/static"))
    variables = shared.Shared(app, os.path.join(workingDIR, "data/config.json"))
    MainView.register(app, init_argument=variables)
    BackendView.register(app, init_argument=variables)
    app.run(host="0.0.0.0", port="1337", debug=True)