import json
import psutil as psu
from swissmodel import SwissModel

class Shared(object):
    
    def __init__(self, app, configurationPath):
        configurationFile = open(configurationPath, "r")
        configurationFile.seek(0)
        configurationSerialized = configurationFile.read()
        configurationFile.close()
        c = json.loads(configurationSerialized)
        for element in c:
            self.__dict__[element] = c[element]
        print("Configurations Loaded")
        
        self.swissmodel = SwissModel()
        self.tasks = {}

        self.app = app

        def get_hardware_stats():
            return self.getHardwareStats()
        self.app.jinja_env.globals.update(getHardwareStats=get_hardware_stats)


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