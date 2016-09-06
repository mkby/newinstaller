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

import base64
import json
from common import *

def run():
    """ create trafodion user, bashrc, setup passwordless SSH """
    dbcfgs = json.loads(dbcfgs_json)

    TRAF_USER = dbcfgs['traf_user']
    TRAF_PWD = base64.b64decode(dbcfgs['traf_pwd'])
    TRAF_GROUP = TRAF_USER
    TRAF_HOME = cmd_output('cat /etc/default/useradd |grep HOME |cut -d "=" -f 2').strip()
    TRAF_USER_DIR = '%s/%s' % (TRAF_HOME, TRAF_USER)
    SQ_ROOT = '%s/%s-%s' % (TRAF_USER_DIR, dbcfgs['traf_basename'], dbcfgs['traf_version'])

    KEY_FILE = '/tmp/id_rsa'
    AUTH_KEY_FILE = '%s/.ssh/authorized_keys' % TRAF_USER_DIR
    SSH_CFG_FILE = '%s/.ssh/config' % TRAF_USER_DIR
    BASHRC_TEMPLATE = '%s/bashrc.template' % TMP_DIR
    BASHRC_FILE = '%s/.bashrc' % TRAF_USER_DIR
    ULIMITS_FILE = '/etc/security/limits.d/%s.conf' % TRAF_USER
    HSPERFDATA_FILE = '/tmp/hsperfdata_trafodion'

    # create trafodion user and group
    if not cmd_output('getent group %s' % TRAF_GROUP):
        run_cmd('groupadd %s > /dev/null 2>&1' % TRAF_GROUP)

    if not cmd_output('getent passwd %s' % TRAF_USER):
        run_cmd('useradd --shell /bin/bash -m %s -g %s --password "$(openssl passwd %s)"' % (TRAF_USER, TRAF_GROUP, TRAF_PWD))

    # set ssh key
    run_cmd_as_user(TRAF_USER, 'echo -e "y" | ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa')
    # the key is generated in copy_file script running on the installer node
    run_cmd('cp %s{,.pub} %s/.ssh/' % (KEY_FILE, TRAF_USER_DIR))

    run_cmd_as_user(TRAF_USER, 'cat ~/.ssh/id_rsa.pub > %s' % AUTH_KEY_FILE)
    run_cmd('chmod 644 %s' % AUTH_KEY_FILE)

    ssh_cfg = 'StrictHostKeyChecking=no\nNoHostAuthenticationForLocalhost=yes\n'
    with open(SSH_CFG_FILE, 'w') as f:
        f.write(ssh_cfg)
    run_cmd('chmod 600 %s' % SSH_CFG_FILE)

    run_cmd('chown -R %s:%s %s/.ssh/' % (TRAF_USER, TRAF_GROUP, TRAF_USER_DIR))

    # set bashrc
    nodes = dbcfgs['node_list'].split(',')
    change_items = {
    '{{ sq_home }}': SQ_ROOT,
    '{{ node_list }}': ' '.join(nodes),
    '{{ node_count }}':str(len(nodes)),
    '{{ my_nodes }}': ' -w ' + ' -w '.join(nodes)
    }

    mod_file(BASHRC_TEMPLATE, change_items)
        
    # backup bashrc if exsits
    if os.path.exists(BASHRC_FILE):
        run_cmd('cp %s %s.bak' % ((BASHRC_FILE,) *2))

    # copy bashrc to trafodion's home
    run_cmd('cp %s/bashrc.template %s' % (TMP_DIR, BASHRC_FILE))
    run_cmd('chown -R %s:%s %s*' % (TRAF_USER, TRAF_GROUP, BASHRC_FILE))

    # set ulimits for trafodion user
    ulimits_config = '''
# Trafodion settings
%s   soft   core unlimited
%s   hard   core unlimited
%s   soft   memlock unlimited
%s   hard   memlock unlimited
%s   soft   nofile 32768
%s   hard   nofile 65536
%s   soft   nproc 100000
%s   hard   nproc 100000
%s   soft nofile 8192
%s   hard nofile 65535
hbase soft nofile 8192
''' % ((TRAF_USER,) * 10)

    with open(ULIMITS_FILE, 'w') as f:
        f.write(ulimits_config)

    # change permission for hsperfdata
    if os.path.exists(HSPERFDATA_FILE):
        run_cmd('chown -R %s:%s %s' % (TRAF_USER, TRAF_GROUP, HSPERFDATA_FILE))

    # clean up unused key file at the last step
    run_cmd('rm -rf %s{,.pub}' % KEY_FILE)

    print 'Setup trafodion user successfully!'

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
