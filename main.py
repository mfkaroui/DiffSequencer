import os
import flask
from multiprocessing.pool import Pool as mpp
from multiprocessing.dummy import Pool as ThreadPool

from viz import views

seqDir = "sequences"
outputDir = "output"
workingDir = os.path.dirname(os.path.realpath(__file__))

seqDir = os.path.join(workingDir, seqDir)
outputDir = os.path.join(workingDir, outputDir)

def validateSequence(s):
    global sm
    return sm.validateSequence(s) is not None

def searchTemplates(s):
    global sm
    return sm.searchTemplates(s)

def getModel(s):
    global sm
    projectID, response, templates = sm.searchTemplates(s)
    templates.sort(key=lambda t: float(t["comment"]["prob"]) if "prob" in t["comment"] else 0.0)
    return sm.buildModel(projectID, templates[0]["id"])

if __name__ == "__main__":
    print("Loading data visualizer...")
    
    views.initializeViews(workingDir)
    #get all sequences in directory
    sequences = {}
    for fileName in os.listdir(seqDir):
        if fileName.endswith(".seq"):
            with open(os.path.join(seqDir, fileName), "r") as fileHandle:
                seq = sm.validateSequence(fileHandle.read().replace("\n", ""))
                if seq is not None:
                    seqPath = os.path.join(outputDir, fileName[:-4])
                    if os.path.isdir(seqPath) == False:
                        os.makedirs(seqPath)
                    sequences[fileName[:-4]] = seq
    sequencevalues = list(sequences.values())
    '''pool = ThreadPool(len(sequencevalues))
    reports = pool.map(getModel, sequencevalues)
    pool.close()
    pool.join()
    del pool

    for sequenceName in sequences:
        seqPath = os.path.join(outputDir, sequenceName)
        sequenceIndex = sequencevalues.index(sequences[sequenceName])
        for f in reports[sequenceIndex].filelist:
            fpath = f.filename.split("/")
            fname = fpath[-1]
            del fpath[-1]
            fpath[0] = seqPath
            fpath = os.path.join(*fpath)
            if os.path.isdir(fpath) == False:
                os.makedirs(fpath)
            data = reports[sequenceIndex].read(f.filename)
            with open(os.path.join(fpath, fname), "wb") as fhandle:
                fhandle.seek(0)
                fhandle.truncate()
                fhandle.write(data)'''
    print("Found " + str(len(sequences)) + " sequences")
    fragmentDir = os.path.join(outputDir, "Fragments")
    if os.path.isdir(fragmentDir) == False:
        os.mkdir(fragmentDir)
    maxSearchLength = int(input("What is the maximum search length you would like? (Must be at least 30) "))
    searchStride = int(input("What is the search stride that you would like? "))
    print("Comparing sequences for shared fragments...")
    histogram = {}
    for sequence in sequences:
        if sequence not in histogram:
            histogram[sequence] = {}
        for comparisonSequence in sequences:
            if comparisonSequence != sequence:
                if comparisonSequence not in histogram[sequence]:
                    histogram[sequence][comparisonSequence] = {}
                maxPermutationlen = min(min(len(sequences[sequence]), len(sequences[comparisonSequence])), maxSearchLength)
                for currentLength in range(30, maxPermutationlen + 1):
                    print("[" + sequence + " vs " + comparisonSequence + "] Comparing " + str(currentLength) +  " length sequences...")
                    for i in range(0, len(sequences[sequence]), searchStride):
                        endi = i + currentLength
                        if endi <= len(sequences[sequence]):
                            subseq = sequences[sequence][i:endi]
                            if subseq not in histogram[sequence][comparisonSequence]:
                                count = sequences[comparisonSequence].count(subseq)
                                if count > 0:
                                    histogram[sequence][comparisonSequence][subseq] = count
                        else:
                            break
                subseqs = list(histogram[sequence][comparisonSequence].keys())
                for subseq in subseqs:
                    for compsubseq in subseqs:
                        if len(subseq) < len(compsubseq):
                            if compsubseq.count(subseq) > 0:
                                histogram[sequence][comparisonSequence].pop(subseq)
                                break
    print("Flattening results and validating sequences...")
    flatSubSeqs = []
    for sequence in sequences:
        for comparisonSequence in sequences:
            if comparisonSequence != sequence:
                subseqs = list(histogram[sequence][comparisonSequence].keys())
                for subseq in subseqs:
                    if subseq not in flatSubSeqs:
                        seq = sm.validateSequence(subseq)
                        if seq is not None:
                            flatSubSeqs.append(seq)
    print("Found " + str(len(flatSubSeqs)) + " shared sequence fragments")
    print("Getting models for sequence fragments...")
    pool = ThreadPool(len(flatSubSeqs))
    reports = pool.map(getModel, flatSubSeqs)
    pool.close()
    pool.join()
    del pool

    for i in range(len(flatSubSeqs)):
        fdir = os.path.join(fragmentDir, str(i))
        if os.path.isdir(fdir) == False:
            os.mkdir(fdir)
        for f in reports[i].filelist:
            fpath = f.filename.split("/")
            fname = fpath[-1]
            del fpath[-1]
            fpath[0] = fdir
            fpath = os.path.join(*fpath)
            if os.path.isdir(fpath) == False:
                os.makedirs(fpath)
            data = reports[i].read(f.filename)
            with open(os.path.join(fpath, fname), "wb") as fhandle:
                fhandle.seek(0)
                fhandle.truncate()
                fhandle.write(data)

    