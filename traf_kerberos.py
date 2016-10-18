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

import sys
import re
import json
import socket
from common import run_cmd, cmd_output, err

def run():
    """ setup Kerberos security """
    dbcfgs = json.loads(dbcfgs_json)

    distro = dbcfgs['distro']
    admin_principal = dbcfgs['admin_principal']
    admin_passwd = dbcfgs['kdcadmin_pwd']
    kdc_server = dbcfgs['kdc_server']
    # maxlife = dbcfgs['max_lifetime']
    # max_renewlife = dbcfgs['max_renew_lifetime']
    maxlife = '24hours'
    max_renewlife = '7days'
    kadmin_cmd = 'kadmin -p %s -w %s -s %s -q' % (admin_principal, admin_passwd, kdc_server)

    host_name = socket.getfqdn()
    traf_user = dbcfgs['traf_user']
    hdfs_user = 'hdfs'
    hbase_user = 'hbase'
    realm = re.match('.*@(.*)', admin_principal).groups()[0]
    traf_principal = '%s/%s@%s' % (traf_user, host_name, realm)

    ### setting start ###
    print 'Checking KDC server connection'
    run_cmd('%s listprincs' % kadmin_cmd)

    # create principals and keytabs for trafodion user
    principal_exists = cmd_output('%s listprincs | grep -c %s' % (kadmin_cmd, traf_principal))
    if int(principal_exists) == 0: # not exist
        run_cmd('%s \'addprinc -randkey %s\'' % (kadmin_cmd, traf_principal))

    # Adjust principal's maxlife and maxrenewlife
    run_cmd('%s \'modprinc -maxlife %s -maxrenewlife %s\' %s >/dev/null 2>&1' % (kadmin_cmd, maxlife, max_renewlife, traf_principal))

    # create keytab for trafodion
    # TODO: need skip add keytab if exist?
    traf_keytab_dir = '/etc/%s/keytab' % traf_user
    run_cmd('mkdir -p %s' % traf_keytab_dir)

    traf_keytab = '%s/%s.keytab' % (traf_keytab_dir, traf_user)

    print 'Create keytab file for hdfs/hbase/trafodion user'
    run_cmd('%s \'ktadd -k %s %s\'' % (kadmin_cmd, traf_keytab, traf_principal))

    # it's difficult to get the current using keytab file in CDH distro
    # so temporarily create principals for hdfs/hbase user using trafodion principal
    run_cmd('sudo -u %s kinit -kt %s %s' % (hdfs_user, traf_keytab, traf_principal))
    run_cmd('sudo -u %s kinit -kt %s %s' % (hbase_user, traf_keytab, traf_principal))

    # set permission after kinit for hdfs/hbase user
    run_cmd('chown %s %s' % (traf_user, traf_keytab))

    print 'Done creating principals and keytabs'

    kinit_bashrc = """

# ---------------------------------------------------------------
# if needed obtain and cache the Kerberos ticket-granting ticket
# start automatic ticket renewal process
# ---------------------------------------------------------------
klist -s >/dev/null 2>&1
if [[ $? -eq 1 ]]; then
    kinit -kt %s %s >/dev/null 2>&1
fi

# ---------------------------------------------------------------
# Start trafodion kerberos ticket manager process
# ---------------------------------------------------------------
$MY_SQROOT/sql/scripts/krb5service start >/dev/null 2>&1
""" % (traf_keytab, traf_principal)

    traf_bashrc = '/home/%s/.bashrc' % traf_user
    with open(traf_bashrc, 'a') as f:
        f.write(kinit_bashrc)

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
