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
import re
import sys
import json
import socket
from constants import TRAF_CFG_FILE, DEF_PORT_FILE, DEF_HBASE_HOME
from common import err, run_cmd, cmd_output, append_file, mod_file, \
                   ParseXML, ParseInI

def run():
    dbcfgs = json.loads(dbcfgs_json)

    distro = dbcfgs['distro']
    traf_home = os.environ['TRAF_HOME']
    traf_ver = dbcfgs['traf_version']
    hbase_xml_file = dbcfgs['hbase_xml_file']

    mgblty_install_dir = '%s/mgblty' % traf_home
    dbmgr_install_dir = '%s/dbmgr-%s' % (traf_home, traf_ver)

    mgblty_tools_dir = '%s/opentsdb/tools' % mgblty_install_dir
    bosun_config = '%s/bosun/conf/bosun.conf' % mgblty_install_dir
    opentsdb_config = '%s/opentsdb/etc/opentsdb/opentsdb.conf' % mgblty_install_dir
    hbase_collector = '%s/tcollector/collectors/0/hbase_master.py' % mgblty_install_dir
    regionserver_collector = '%s/tcollector/collectors/0/hbase_regionserver.py' % mgblty_install_dir
    start_stop = '%s/tcollector/startstop' % mgblty_install_dir

    if dbcfgs['ldap_security'] == 'Y':
        db_admin_user = dbcfgs['db_admin_user']
        db_admin_pwd = dbcfgs['db_admin_pwd']
    else:
        db_admin_user = 'admin'
        db_admin_pwd = 'admin'

    ports = ParseInI(DEF_PORT_FILE, 'ports').load()
    rest_port = ports['rest_port']
    dm_http_port = ports['dm_http_port']
    dm_https_port = ports['dm_https_port']
    tsd_port = ports['tsd_port']
    bosun_http_port = ports['bosun_http_port']
    dcs_master_port = ports['dcs_master_port']
    dcs_info_port = ports['dcs_info_port']

    nodes = dbcfgs['node_list'].split(',')
    dcs_master_host = nodes[0]
    if dbcfgs['dcs_ha'] == 'Y':
        dcs_master_host = dbcfgs['dcs_floating_ip']

    first_node = nodes[0]
    local_host = socket.gethostname()

    # edit bosun.conf
    mod_file(bosun_config, {'tsdbHost = .*':'tsdbHost = %s:%s' % (dcs_master_host, tsd_port)})

    # edit opentsdb config
    hb = ParseXML(hbase_xml_file)
    zk_hosts = hb.get_property('hbase.zookeeper.quorum')
    timezone = cmd_output('%s/tools/gettimezone.sh' % traf_home).split('\n')[0]

    mod_file(opentsdb_config,
             {'tsd.network.port = .*':'tsd.network.port = %s' % tsd_port,
              'tsd.core.timezone = .*':'tsd.core.timezone = %s' % timezone,
              'tsd.storage.hbase.zk_quorum = .*':'tsd.storage.hbase.zk_quorum = %s' % zk_hosts})

    if dbcfgs['secure_hadoop'].upper() == 'Y':
        realm = re.match('.*@(.*)', dbcfgs['admin_principal']).groups()[0]
        tsdb_secure_config = """
# ------- Properties to access secure hbase -------
hbase.security.auth.enable=true
hbase.security.authentication=kerberos
hbase.kerberos.regionserver.principal=hbase/_HOST@%s
hbase.sasl.clientconfig=Client
""" % realm
        append_file(opentsdb_config, tsdb_secure_config)

    # additional config for HDP distro
    if 'HDP' in distro:
        hm_info_port = hb.get_property('hbase.master.info.port')
        rs_info_port = hb.get_property('hbase.regionserver.info.port')
        if dbcfgs['secure_hadoop'].upper() == 'Y':
            hbase_basedir = '/hbase-secure'
        else:
            hbase_basedir = '/hbase-unsecure'
        mod_file(opentsdb_config,
                 {'tsd.storage.hbase.zk_basedir = .*':'tsd.storage.hbase.zk_basedir = %s' % hbase_basedir})
        # edit hbase master collector
        mod_file(hbase_collector, {'60010':hm_info_port})
        # edit hbase regionserver collector
        mod_file(regionserver_collector, {'60030':rs_info_port})

    # edit start stop
    mod_file(start_stop, {'TSDPORT=.*':'TSDPORT=%s' % tsd_port})

    # set 755 for bosun bin
    run_cmd('chmod 755 %s/bosun/bin/bosun-linux-amd64' % mgblty_install_dir)

    # edit trafodion config
    append_file(TRAF_CFG_FILE, 'export PATH=$PATH:%s/jython2.7.0/bin' % mgblty_install_dir)
    append_file(TRAF_CFG_FILE, 'export MGBLTY_INSTALL_DIR=%s' % mgblty_install_dir)
    append_file(TRAF_CFG_FILE, 'export DBMGR_INSTALL_DIR=%s' % dbmgr_install_dir)

    # run below commands on first node only
    if first_node in local_host:
        # create opentsdb table in hbase
        if dbcfgs.has_key('hbase_home'):
            hbase_home = dbcfgs['hbase_home']
        else:
            hbase_home = DEF_HBASE_HOME
        run_cmd('export HBASE_HOME=%s; export COMPRESSION=SNAPPY; %s/create_table.sh' % (DEF_HBASE_HOME, mgblty_tools_dir))
        # register metrics
        run_cmd('export MGBLTY_INSTALL_DIR=%s; %s/register_metrics.sh' % (mgblty_install_dir, mgblty_tools_dir))

    # run configure.py
    run_cmd('%s/bin/configure.py --httpport %s --httpsport %s --dcshost %s --dcsport %s \
    --password dbmgr23400 --dcsinfoport %s --resthost %s --restport %s --tsdhost %s --tsdport %s \
    --bosunhost %s --bosunport %s --timezone %s --adminuser %s --adminpassword %s' %
            (dbmgr_install_dir,
             dm_http_port,
             dm_https_port,
             dcs_master_host,
             dcs_master_port,
             dcs_info_port,
             local_host,
             rest_port,
             dcs_master_host,
             tsd_port,
             dcs_master_host,
             bosun_http_port,
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
