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

### this script should be run on first node with trafodion user ###

import sys
import json
from common import run_cmd, err

def run():
    """ start trafodion instance """
    dbcfgs = json.loads(dbcfgs_json)

    run_cmd('sqstart')

    run_cmd('echo "initialize trafodion;" | sqlci')

    if dbcfgs['ldap_security'] == 'Y':
        run_cmd('echo "initialize authorization; alter user DB_ROOT set external name \"%s\";" | sqlci' % dbcfgs['db_root_user'])
# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
