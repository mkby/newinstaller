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

import os
import sys
import re
import json
from constants import EDB_CGROUP_NAME, CGRULES_CONF_FILE
from common import err, run_cmd, get_default_home

def run():
    dbcfgs = json.loads(dbcfgs_json)

    ### cgroup settings ###
    if dbcfgs['multi_tenancy'] == 'Y':
        cpu_pct = dbcfgs['cgroups_cpu_pct']
        mem_pct = dbcfgs['cgroups_mem_pct']

        home_dir = get_default_home()
        if dbcfgs.has_key('home_dir'):
            home_dir = dbcfgs['home_dir']

        traf_user = dbcfgs['traf_user']
        traf_dirname = dbcfgs['traf_dirname']
        traf_home = '%s/%s/%s' % (home_dir, traf_user, traf_dirname)

        # make sure cgroup service is running
        run_cmd('service cgconfig restart')

        esgyn_cgrules = '%s cpu,memory %s/' % (traf_user, EDB_CGROUP_NAME)
        mod_file(CGRULES_CONF_FILE, esgyn_cgrules)

        run_cmd('service cgred restart')

        run_cmd('%s/sql/scripts/edb_cgroup_cmd --add --pcgrp %s --cpu_pct %s --mem_pct %s' % (traf_home, EDB_CGROUP_NAME, cpu_pct, mem_pct))
# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
