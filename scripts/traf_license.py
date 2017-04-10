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

### this script should be run on local node ###

import os
import json
import sys
from constants import SCRIPTS_DIR, TRAF_CFG_DIR, TRAF_LICENSE_FILE
from common import Remote, run_cmd, cmd_output, err, info, get_sudo_prefix

def run(user, pwd):
    dbcfgs = json.loads(dbcfgs_json)

    nodes = dbcfgs['node_list'].split(',')
    node_count = len(nodes)
    traf_package = dbcfgs['traf_package']
    license_file = dbcfgs['license_file']

    def check_license():
        info('checking license file')
        if not os.path.exists(SCRIPTS_DIR + '/decoder'):
            err('Missing the decoder program')
        else:
            #get license type
            license_type = cmd_output('%s/decoder -t -f %s' % (SCRIPTS_DIR, license_file))

            if license_type != 'INTERNAL':
                #check support node number
                nodes = cmd_output('%s/decoder -n -f %s' % (SCRIPTS_DIR, license_file))
                if node_count > nodes:
                    err('Current number of nodes does not match allowed number of nodes')

                #check support version
                esgyn_version = cmd_output('%s/decoder -p -f %s' % (SCRIPTS_DIR, license_file))
                esgyn_version = '_' + cmd_output('echo %s | awk \'{print tolower($0)}\'' % esgyn_version) + '_'
                if esgyn_version not in traf_package:
                    err('License version doesn\'t match package')

                #scheck expire date
                expire_day = cmd_output('%s/decoder -e -f %s' % (SCRIPTS_DIR, license_file))
                current_day = cmd_output('echo $(($(date --utc --date "$1" +\%s)/86400))')
                days_left = int(expire_day) - int(current_day)
                if days_left < 0:
                    err('License expired!')
                elif days_left < 30:
                    info('Warning: Days left of license %s' % days_left)

    def copy_license():
        info('copying license file to all nodes')
        tmp_license_file = '/tmp/esgyndb_license'
        run_cmd('cp %s %s' % (license_file, tmp_license_file))

        sudo_prefix = get_sudo_prefix()
        if user:
            if user == 'root':
                sudo_prefix = ''
            else:
                sudo_prefix = 'sudo -n'
        remotes = [Remote(node, user=user, pwd=pwd) for node in nodes]
        for remote in remotes:
            remote.execute('%s rm -rf %s; %s mkdir -p %s; %s chmod 777 %s' % \
                (sudo_prefix, TRAF_LICENSE_FILE, sudo_prefix, TRAF_CFG_DIR, sudo_prefix, TRAF_CFG_DIR))
            remote.copy([tmp_license_file], remote_folder=TRAF_CFG_DIR)
            remote.execute('chmod +r %s' % TRAF_LICENSE_FILE)

        run_cmd('rm -rf %s' % tmp_license_file)

    check_license()
    copy_license()

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')

try:
    pwd = sys.argv[2]
except IndexError:
    user = pwd = ''

try:
    user = sys.argv[3]
except IndexError:
    user = ''

run(user, pwd)
