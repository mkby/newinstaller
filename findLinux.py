#!/usr/bin/env python

import platform
from common import *
import os

path=os.path.dirname(os.path.abspath(__file__))
configFile = ParseJson(path + '/discover_config.json')

def getVersion():

    linuxType=str(platform.dist()[0])
    linuxVersion=str(platform.dist()[1])
   
    compareType(linuxType)    
  
    setConfigs("linuxType", linuxType)
    setConfigs("linuxVersion", linuxVersion)

def setConfigs(key, value):
 
    configFile.setConfig(key, value);

def compareType(linuxType):
    config = ParseJson(path + '/versionSupport.json').jload()
    supportedLinux = config['linuxVersions']
    if linuxType.lower() in supportedLinux:
        print "%s is installed and it is supported" % (linuxType)
        get_logger().info(linuxType + ' installed and supported')
    else:
        print "%s is not supported. Please install a supported version: %s" % (linuxType, supportedLinux)
        get_logger().error(linuxType + ' installed and not supported')
        get_logger().error('Use a supported linux type ' + supportedLinux)

if __name__ == '__main__':

   getVersion()
