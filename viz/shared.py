import json

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
        