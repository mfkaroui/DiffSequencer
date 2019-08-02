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


if __name__ == "__main__":
    views.initializeViews(workingDir)