#!/usr/bin/env python

from common import *

import os
import glob
import getpass

path=os.path.dirname(os.path.abspath(__file__))

listOfNodes = ParseJson(path + '/nodes.json').jload()['nodes']
path = os.getcwd()
allfiles=glob.glob(path + '/*')

for node in listOfNodes:
    print info(node)

    remote = Remote(node)

    remote.copy(allfiles)

    print str(remote._execute('./discover.py')[1])


