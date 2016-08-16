#!/usr/bin/env python

import platform
from common import *


configFile = ParseJson("discover_config.json")

def getVersion():

    linuxType=str(platform.dist()[0])
    linuxVersion=str(platform.dist()[1])
   
    compareType(linuxType)    
  
    setConfigs("linuxType", linuxType)
    setConfigs("linuxVersion", linuxVersion)

def setConfigs(key, value):
 
    configFile.setConfig(key, value);

def compareType(linuxType):
    config = ParseJson("versionSupport.json").jload()
    supportedLinux = config['linuxVersions']
    if linuxType.lower() in supportedLinux:
        print "COOL"
    else:
        print "Not cool" 

if __name__ == '__main__':

   getVersion()
