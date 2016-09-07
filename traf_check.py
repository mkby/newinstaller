#!/usr/bin/env python

# @@@ START COPYRIGHT @@@
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# @@@ END COPYRIGHT @@@

### this script should be run on all nodes with sudo user ###

import re
import json
import sys
import os
import platform
from common import run_cmd, cmd_output, ParseJson, err, TMP_DIR

def run():
    """ check system envs """

    dbcfgs = json.loads(dbcfgs_json)
    support_ver = ParseJson('%s/version.json' % TMP_DIR).jload()

    # check Linux version
    os_dist, os_ver = platform.dist()[:2]

    if os_dist not in support_ver['linux']:
        err('Linux distribution %s doesn\'t support' % os_dist)
    else:
        if not os_ver.split('.')[0] in support_ver[os_dist]:
            err('%s version %s doesn\'t support' % (os_dist, os_ver))

    # check sudo access
    run_cmd('sudo -n echo -n "check sudo access" > /dev/null 2>&1')

    # check hbase xml exists
    hbase_xml_file = dbcfgs['hbase_xml_file']
    if not os.path.exists(hbase_xml_file):
        err('HBase xml file is not found')

    # check JDK version
    jdk_ver = cmd_output('javac -version') # javac 1.7.0_85
    print jdk_ver
    try:
        jdk_ver = re.search('(\d\.\d)', jdk_ver).groups()[0]
    except AttributeError:
        err('No JDK found')

    if dbcfgs['req_java8'] == 'Y': # only allow JDK1.8
        support_ver['java'] = ['1.8']

    if jdk_ver not in support_ver['java']:
        err('Unsupported JDK version %s' % jdk_ver)


    # check previous installed trafodion processes
    mon_process = cmd_output('ps -ef|grep -c "monitor COLD"')
    if int(mon_process) > 1:
        err('Trafodion process is found, please stop it first')

    # check Apache HBase version if Apache Hadoop


# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
