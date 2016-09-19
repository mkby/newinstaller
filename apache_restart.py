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

### this script should be run on first node with sudo user ###

import json
from common import run_cmd, err

dbcfgs = json.loads(dbcfgs_json)

def run():
    if 'APACHE' in dbcfgs['distro']:
        hadoop_home = dbcfgs['hadoop_home']
        hbase_home = dbcfgs['hbase_home']
        # stop
        run_cmd(hbase_home + '/bin/stop_hbase.sh')
        run_cmd(hadoop_home + '/sbin/stop_dfs.sh')
        # start
        run_cmd(hadoop_home + '/sbin/start_dfs.sh')
        run_cmd(hbase_home + '/bin/start_hbase.sh')
    else:
        print 'no apache distribution found, skipping'

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
