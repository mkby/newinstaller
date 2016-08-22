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
    compareVersion(linuxType, linuxVersion)
 
    setConfigs("linuxType", linuxType)
    setConfigs("linuxVersion", linuxVersion)

def setConfigs(key, value):
 
    configFile.setConfig(key, value);

def compareVersion(linuxType, linuxVersion):
    supportedVersion = ParseJson(path + '/versionSupport.json').jload()[linuxType + 'Versions']
    if linuxVersion[0] in supportedVersion:
       print "%s is installed and it is supported" % (linuxVersion)
       get_logger().info(linuxVersion + ' installed and supported')
    else:
       print "%s is not supported. Please install a supported version: %s" % (linuxVersion, supportedVersion)
       get_logger().err2(linuxType + ' installed and not supported')
       get_logger().err2('Use a supported linux version ' + supportedVersion)
 

def compareType(linuxType):
    supportedLinux = ParseJson(path + '/versionSupport.json').jload()['linuxVersions']
    if linuxType.lower() in supportedLinux:
        print "%s is installed and it is supported" % (linuxType)
        get_logger().info(linuxType + ' installed and supported')
    else:
        print "%s is not supported. Please install a supported version: %s" % (linuxType, supportedLinux)
        get_logger().err2(linuxType + ' installed and not supported')
        get_logger().err2('Use a supported linux type ' + supportedLinux)

if __name__ == '__main__':

   getVersion()
