import json
import psutil as psu
import os
from swissmodel import SwissModel
from multiprocessing import Manager

class Shared(object):
    
    def __init__(self, app, outputPath, configurationPath):
        configurationFile = open(configurationPath, "r")
        configurationFile.seek(0)
        configurationSerialized = configurationFile.read()
        configurationFile.close()
        c = json.loads(configurationSerialized)
        for element in c:
            self.__dict__[element] = c[element]
        print("Configurations Loaded")
        
        self.nworkers = psu.cpu_count()

        self.outputPath = outputPath

        self.swissmodel = SwissModel()
        self.tasks = {}
        self.taskResults = Manager()
        self.sequences = {}

        for f in os.listdir(self.outputPath):
            fullPath = os.path.join(self.outputPath, f)
            if os.path.isdir(fullPath) and "report.html" in list(os.listdir(fullPath)):
                with open(os.path.join(fullPath, "model/01/report.json"), "r") as modelReportFile:
                    modelReportFile.seek(0)
                    modelReportSerialized = modelReportFile.read()
                    modelReportDeserialized = json.loads(modelReportSerialized)
                    self.sequences[f] = modelReportDeserialized["modelling"]["trg_seq"]

        self.sequenceFragments = {}

        self.app = app

        def get_hardware_stats():
            return self.getHardwareStats()
        self.app.jinja_env.globals.update(getHardwareStats=get_hardware_stats)
        self.app.jinja_env.globals.update(sequences=self.sequences)
        self.app.jinja_env.globals.update(sequenceFragments=self.sequenceFragments)

    def getHardwareStats(self):
        return {
            "cpu_count_physical" : psu.cpu_count(False),
            "cpu_count_logical" : psu.cpu_count(),
            "cpu_freq" : dict(psu.cpu_freq()._asdict()),
            "cpu_percent_total" : psu.cpu_percent(percpu=False),
            "cpu_percent" : psu.cpu_percent(percpu=True),
            "swap_memory" : dict(psu.swap_memory()._asdict()),
            "virtual_memory" : dict(psu.virtual_memory()._asdict())
        }

    def saveModel(self, zipFile, sequenceName):
        seqPath = os.path.join(self.outputPath, sequenceName)
        for f in zipFile.filelist:
            fpath = f.filename.split("/")
            fname = fpath[-1]
            del fpath[-1]
            fpath[0] = seqPath
            fpath = os.path.join(*fpath)
            if os.path.isdir(fpath) == False:
                os.makedirs(fpath)
            data = zipFile.read(f.filename)
            with open(os.path.join(fpath, fname), "wb") as fhandle:
                fhandle.seek(0)
                fhandle.truncate()
                fhandle.write(data)