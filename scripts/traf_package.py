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

import sys
import json
from common import run_cmd, cmd_output, err, get_default_home

def run():
    dbcfgs = json.loads(dbcfgs_json)

    home_dir = get_default_home()
    if dbcfgs.has_key('home_dir'):
        home_dir = dbcfgs['home_dir']

    traf_user = dbcfgs['traf_user']
    traf_group = cmd_output('id -ng %s' % traf_user)
    traf_dirname = dbcfgs['traf_dirname']
    traf_home = '%s/%s/%s' % (home_dir, traf_user, traf_dirname)

    # untar traf package, package comes from copy_files.py
    traf_package_file = '/tmp/' + dbcfgs['traf_package'].split('/')[-1]
    run_cmd('mkdir -p %s' % traf_home)
    run_cmd('tar xf %s -C %s' % (traf_package_file, traf_home))

    run_cmd('chmod 700 %s' % traf_home)
    run_cmd('chown -R %s:%s %s' % (traf_user, traf_group, traf_home))

    run_cmd('rm -rf %s' % traf_package_file)
    print 'Trafodion package extracted successfully!'

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
