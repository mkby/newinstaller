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
import os
import json
import sys
import time
from constants import SCRIPTS_DIR
from common import cmd_output, run_cmd

INTERVAL = 5

def run():
    try:
        dbcfgs_json = sys.argv[1]
    except IndexError:
        err('No db config found')

    dbcfgs = json.loads(dbcfgs_json)
    hosts = dbcfgs['node_list'].split(',')

    # start server on 1,3,5... and client on 2,4,6...
    # that is, 1<-2, 3<-4, 5<-6
    # ignore checking the last node if node count is odd
    servers = hosts[::2]
    clients = hosts[1::2]

    result = ''
    local_host = run_cmd('hostname -s')
    if local_host in servers:
        os.popen('%s/iperf -s &' % SCRIPTS_DIR)
        time.sleep(INTERVAL+1)
        # donnot check return value
        cmd_output("ps -ef|grep 'iperf -s'|grep -v grep|awk '{print $2}'|xargs kill -9")

    elif local_host in clients:
        # TODO: should use IP ADDR
        time.sleep(1)
        server_host = servers[clients.index(local_host)]
        result = run_cmd('%s/iperf -c %s -t %s' % (SCRIPTS_DIR, server_host, INTERVAL))
        #'[  3]  0.0- 3.0 sec  6.39 GBytes  18.3 Gbits/sec'
        try:
            result = re.search(r'.* (\d+.*/sec)', result).groups()[0]
            result += ', %s => %s' % (local_host, server_host)
        except:
            result = 'N/A'

    print result

# main
if __name__ == '__main__':
    run()
