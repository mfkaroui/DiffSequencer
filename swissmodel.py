from urllib.parse import urlencode
import urllib3 #communicating with swiss model website servers
import requests
import json #javascript object notation, read comms from SM
import re #regex, regular expressions; looking for particular information from data
from datetime import datetime as dt 
import time #handling time stamps
import io 
import zipfile as zf #filemanagement libraries 

class SwissModel:
    baseurl = "https://swissmodel.expasy.org/interactive/"
    validateSequenceCache = {} #dictionary, makes sure sequence is valid before sending to SM
    def __init__(self): #first variable in function belonging to a class has to be called 'self'
        #Get session and tokens
        response = requests.get(self.baseurl) #grabbing variable inside the class 
        if response.ok == True:
            self.sessionCookies = response.cookies
        else:
            self.sessionCookies = None

    def validateSequence(self, sequence):
        if sequence in self.validateSequenceCache:
            return sequence if self.validateSequenceCache[sequence] else None
        else:
            response = requests.post(self.baseurl + "validate", {"target":sequence, "is_alignment":False, "csrfmiddlewaretoken":self.sessionCookies['csrftoken']}, headers={"Referer": "https://swissmodel.expasy.org/interactive"}, cookies=self.sessionCookies)
            if response.ok == True:
                response = json.loads(response.text) #the response from SM
                if "error" in response:
                    self.validateSequenceCache[sequence] = False
                    print("[SwissModel] Error sequence is invalid - " + sequence)
                    return None
                else:
                    self.validateSequenceCache[response["sequence"][0]["target"]] = True
                    print("[SwissModel] Sequence is valid - " + response["sequence"][0]["target"])
                    return response["sequence"][0]["target"]
    # validating entire sequence and getting a response back from SM saying this input is valid

    def searchTemplates(self, sequence):
        response = requests.post(self.baseurl + "interactive", {"target":sequence, "is_alignment":False, "csrfmiddlewaretoken":self.sessionCookies['csrftoken']}, headers={"Referer": "https://swissmodel.expasy.org/interactive"}, cookies=self.sessionCookies)
        if response.ok == True:
            matches = re.findall(r"/interactive/([a-z,A-Z,0-9]*)/", response.text)
            projectID = matches[0]
            print("[SwissModel] [" + projectID + "] Searching templates for - " + sequence)
            progress = []
            while True:
                timestamp = int(dt.utcnow().timestamp())
                response = requests.get(self.baseurl + projectID + "/models/automodel_poll?t=" + str(timestamp), headers={"Referer": "https://swissmodel.expasy.org/interactive"}, cookies=self.sessionCookies)
                if response.ok == True:
                    response = json.loads(response.text)
                    if response["tpl_search_status"] == "COMPLETED":
                        print("[SwissModel] [" + projectID + "] Search progress - Completed")
                        print("[SwissModel] [" + projectID + "] Retrieving templates.")
                        templates = requests.get(self.baseurl + projectID + "/templates.json", headers={"Referer": "https://swissmodel.expasy.org/interactive"}, cookies=self.sessionCookies)
                        if templates.ok == True:
                            templates = json.loads(templates.text)
                            for i in range(len(templates)):
                                templates[i]["comment"] = json.loads("{\"" + templates[i]["comment"].replace(" ", "\"").replace("=", "\":") + "}")
                            print("[SwissModel] [" + projectID + "] Recieved " + str(len(templates)) + " templates.") #parsing for comments, need that for sorting the templates
                            return projectID, response, templates
                        break
                    else:
                        for p in response["tpl_search_progress"]["progress"]:
                            if p not in progress:
                                print("[SwissModel] [" + projectID + "] Search progress - " + p) 
                                progress.append(p) #status of the template search not completed, so we store the progress
                else:
                    break
                time.sleep(2)  
        return None, None, None
            
    def buildModel(self, projectID, templateID):
        print("[SwissModel] [" + projectID + "] Building model using template - " + templateID)
        response = requests.post(self.baseurl + projectID + "/models/", {"selection":templateID, "matchOligoState":templateID+"\tprediction", "get_model_id":"1", "csrfmiddlewaretoken":self.sessionCookies['csrftoken']}, headers={"Referer": self.baseurl + projectID + "/templates/"}, cookies=self.sessionCookies)
        if response.ok == True:
            response = json.loads(response.text)
            modelID = response[0]
            while True:
                timestamp = int(dt.utcnow().timestamp())
                response = requests.get(self.baseurl + projectID + "/models/" + modelID + "/check_status?t=" + str(timestamp), headers={"Referer": "https://swissmodel.expasy.org/interactive"}, cookies=self.sessionCookies)
                if response.ok == True:
                    response = json.loads(response.text)
                    if response["status"] == "COMPLETED":
                        print("[SwissModel] [" + projectID + "] Model built")
                        
                        response = requests.get(self.baseurl + projectID + "/models/" + modelID + "/report.zip", headers={"Referer": "https://swissmodel.expasy.org/interactive"}, cookies=self.sessionCookies, stream=True)
                        if response.ok == True:
                            print("[SwissModel] [" + projectID + "] Downloading model...")
                            zipfile = io.BytesIO() #creating a zipfile the report
                            for chunk in response.iter_content(chunk_size=None):
                                zipfile.write(chunk)
                            zipfile.seek(0)
                            uncompressedZipFile = zf.ZipFile(zipfile) #unzipping report  
                            print("[SwissModel] [" + projectID + "] Model Downloaded")
                            return uncompressedZipFile
                else:
                    break
                time.sleep(2)