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

### this script should be run on all nodes with trafodion user ###

import os
import sys
import json
import socket
from common import err, run_cmd, cmd_output, append_file, mod_file, ParseXML

def run():
    dbcfgs = json.loads(dbcfgs_json)

    DISTRO = dbcfgs['distro']
    SQ_ROOT = os.environ['MY_SQROOT']
    BASHRC_FILE = os.environ['HOME'] + '/.bashrc'
    TRAF_VER = dbcfgs['traf_version']
    HBASE_XML_FILE = dbcfgs['hbase_xml_file']

    MGBLTY_INSTALL_DIR = '%s/mgblty' % SQ_ROOT
    DBMGR_INSTALL_DIR = '%s/dbmgr-%s' % (SQ_ROOT, TRAF_VER)

    MGBLTY_TOOLS_DIR = '%s/opentsdb/tools' % MGBLTY_INSTALL_DIR
    #LOGBACK_XML = '%s/opentsdb/etc/opentsdb/logback.xml' % MGBLTY_INSTALL_DIR
    BOSUN_CONFIG = '%s/bosun/conf/bosun.conf' % MGBLTY_INSTALL_DIR
    OPENTSDB_CONFIG = '%s/opentsdb/etc/opentsdb/opentsdb.conf' % MGBLTY_INSTALL_DIR
    HBASE_COLLECTOR = '%s/tcollector/collectors/0/hbase_master.py' % MGBLTY_INSTALL_DIR
    REGIONSERVER_COLLECTOR = '%s/tcollector/collectors/0/hbase_regionserver.py' % MGBLTY_INSTALL_DIR
    START_STOP = '%s/tcollector/startstop' % MGBLTY_INSTALL_DIR

    if dbcfgs['ldap_security'] == 'Y':
        db_admin_user = dbcfgs['db_admin_user']
        db_admin_pwd = dbcfgs['db_admin_pwd']
    else:
        db_admin_user = 'admin'
        db_admin_pwd = 'admin'

    rest_port = '4200'
    dm_http_port = '4205'
    dm_https_port = '4206'
    tsd_port = '5242'
    http_port = '8070'
    dcs_port = '23400'
    dcs_info_port = '24400'

    nodes = dbcfgs['node_list'].split(',')
    dcs_master_host = nodes[0]
    if dbcfgs['dcs_ha'] == 'Y':
        dcs_master_host = dbcfgs['dcs_floating_ip']

    first_node = nodes[0]
    local_host = socket.gethostname()

    # edit bosun.conf
    mod_file(BOSUN_CONFIG, {'tsdbHost = .*':'tsdbHost = %s:%s' % (dcs_master_host, tsd_port)})

    # edit opentsdb config
    hb = ParseXML(HBASE_XML_FILE)
    zk_hosts = hb.get_property('hbase.zookeeper.quorum')
    timezone = cmd_output('%s/tools/gettimezone.sh' % SQ_ROOT).split('\n')[0]

    mod_file(OPENTSDB_CONFIG,
             {'tsd.network.port = .*':'tsd.network.port = %s' % tsd_port,
              'tsd.core.timezone = .*':'tsd.core.timezone = %s' % timezone,
              'tsd.storage.hbase.zk_quorum = .*':'tsd.storage.hbase.zk_quorum = %s' % zk_hosts})

    # additional config for HDP distro
    if 'HDP' in DISTRO:
        hm_info_port = hb.get_property('hbase.master.info.port')
        rs_info_port = hb.get_property('hbase.regionserver.info.port')
        mod_file(OPENTSDB_CONFIG,
                 {'tsd.storage.hbase.zk_basedir = .*':'tsd.storage.hbase.zk_basedir = /hbase-unsecure'})
        # edit hbase master collector
        mod_file(HBASE_COLLECTOR, {'60010':hm_info_port})
        # edit hbase regionserver collector
        mod_file(REGIONSERVER_COLLECTOR, {'60030':rs_info_port})

    # edit start stop
    mod_file(START_STOP, {'TSDPORT=.*':'TSDPORT=%s' % tsd_port})

    # edit logback xml
    #mod_file(LOGBACK_XML, {'/var/log/opentsdb':'../../log'})

    # set 755 for bosun bin
    run_cmd('chmod 755 %s/bosun/bin/bosun-linux-amd64' % MGBLTY_INSTALL_DIR)

    # edit bashrc
    append_file(BASHRC_FILE, 'export PATH=$PATH:%s/jython2.7.0/bin' % MGBLTY_INSTALL_DIR)
    append_file(BASHRC_FILE, 'export MGBLTY_INSTALL_DIR=%s' % MGBLTY_INSTALL_DIR)
    append_file(BASHRC_FILE, 'export DBMGR_INSTALL_DIR=%s' % DBMGR_INSTALL_DIR)

    # run below commands on first node only
    if first_node in local_host:
        # create opentsdb table in hbase
        if dbcfgs.has_key('hbase_home'):
            run_cmd('export HBASE_HOME=%s; export COMPRESSION=GZ; %s/create_table.sh' % (dbcfgs['hbase_home'], MGBLTY_TOOLS_DIR))
        else:
            run_cmd('export HBASE_HOME=/usr; export COMPRESSION=GZ; %s/create_table.sh' % MGBLTY_TOOLS_DIR)
        # register metrics
        run_cmd('export MGBLTY_INSTALL_DIR=%s; %s/register_metrics.sh' % (MGBLTY_INSTALL_DIR, MGBLTY_TOOLS_DIR))

    # run configure.py
    run_cmd('%s/bin/configure.py --httpport %s --httpsport %s --dcshost %s --dcsport %s \
    --password dbmgr23400 --dcsinfoport %s --resthost %s --restport %s --tsdhost %s --tsdport %s \
    --bosunhost %s --bosunport %s --timezone %s --adminuser %s --adminpassword %s' %
            (DBMGR_INSTALL_DIR,
             dm_http_port,
             dm_https_port,
             dcs_master_host,
             dcs_port,
             dcs_info_port,
             local_host,
             rest_port,
             dcs_master_host,
             tsd_port,
             dcs_master_host,
             http_port,
             timezone,
             db_admin_user,
             db_admin_pwd)
           )

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
