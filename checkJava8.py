#!/usr/bin/python


import subprocess
import re
import os

java8="1.8"

pathToJava=os.environ["JAVA_HOME"]
pathToJava = pathToJava + "/bin/" + "java"
javaVersion  = [pathToJava, "-version"]



sp = subprocess.Popen(javaVersion, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

lst_Java=list(sp.communicate())

print lst_Java

lst_Java=re.findall('version "[0-9.]+_[0-9]+"', lst_Java[1])

print lst_Java

if re.search(java8, str(lst_Java)):
   os._exit(0)
else:
   os._exit(-1)

