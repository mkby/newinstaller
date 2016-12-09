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

## This script should be run on all nodes with sudo user ##

import os
import sys
import json
import socket
from common import run_cmd, err, mod_file

HOST_FILE = '/etc/hosts'
SELINUX_FILE = '/etc/selinux/config'
AGENT_CFG_FILE = '/etc/cloudera-scm-agent/config.ini'
REPO_FILE = '/etc/yum.repos.d/cmlocal.repo'
LOCAL_REPO_PTR = """
[cmlocal]
name=cloudera manager local repo
baseurl=http://%s/
enabled=1
gpgcheck=0
"""

CM_PACKAGES = ['oracle-j2sdk1.7',
               'cloudera-manager-server',
               'cloudera-manager-server-db-2',
               'cloudera-manager-agent']

def run():
    dbcfgs = json.loads(dbcfgs_json)

    nodes = dbcfgs['node_list'].split(',')
    etc_hosts = dbcfgs['etc_hosts']

    ### disable selinux temporarily
    run_cmd('setenforce 0')

    ### disable selinux permanently
    mod_file(SELINUX_FILE, {'^SELINUX=.*':'SELINUX=disabled'})

    ### stop iptables
    run_cmd('service iptables stop')

    ### modify /etc/hosts
    with open(HOST_FILE, 'w') as f:
        f.write('#Created by CM installer\n')
        f.write('127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4\n')
        f.write('::1         localhost localhost.localdomain localhost6 localhost6.localdomain6\n')
        f.writelines(etc_hosts)

    ### setup cmlocal repo file
    repo_content = LOCAL_REPO_PTR % (dbcfgs['repo_url'])
    with open(REPO_FILE, 'w') as f:
        f.write(repo_content)

    ### install CM packages
    print 'Installing CM packages...'
    first_node = nodes[0]
    local_host = socket.gethostname()
    # match FQDN
    if first_node in local_host or local_host in first_node:
        # install CM server on first node
        for pkg in CM_PACKAGES:
            run_cmd('yum install -y %s' % pkg)
    else:
        # install cloudera agents
        run_cmd('yum install -y %s' % CM_PACKAGES[0])
        run_cmd('yum install -y %s' % CM_PACKAGES[-1])

    ### clean up local repo file
    os.remove(REPO_FILE)

    ### restart CM on first node
    if first_node in local_host or local_host in first_node:
        ### fix permission for parcel repo folder
        run_cmd('chown cloudera-scm:cloudera-scm /opt/cloudera/parcel-repo/')

        print 'Stopping Cloudera manager server...'
        run_cmd('service cloudera-scm-server stop')
        run_cmd('service cloudera-scm-server-db stop')

        print 'Starting Cloudera manager server...'
        run_cmd('service cloudera-scm-server-db start')
        run_cmd('service cloudera-scm-server start')

    ### modify cloudera agent settings
    mod_file(AGENT_CFG_FILE, {'server_host=.*':'server_host=%s' % first_node})

    ### start cloudera agent
    print 'Starting Cloudera manager agent...'
    run_cmd('service cloudera-scm-agent restart')


# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
