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
from constants import DEF_PORT_FILE
from common import append_file, write_file, mod_file, cmd_output, \
                   ParseInI, ParseXML, err, run_cmd

def run():
    dbcfgs = json.loads(dbcfgs_json)

    traf_home = os.environ['TRAF_HOME']
    traf_ver = dbcfgs['traf_version']
    hbase_xml_file = dbcfgs['hbase_xml_file']

    dcs_install_env = 'export DCS_INSTALL_DIR=%s/dcs-%s' % (traf_home, traf_ver)
    rest_install_env = 'export REST_INSTALL_DIR=%s/rest-%s' % (traf_home, traf_ver)

    dcs_conf_dir = '%s/dcs-%s/conf' % (traf_home, traf_ver)
    dcs_srv_file = dcs_conf_dir + '/servers'
    dcs_master_file = dcs_conf_dir + '/master'
    dcs_bkmaster_file = dcs_conf_dir + '/backup-masters'
    dcs_env_file = dcs_conf_dir + '/dcs-env.sh'
    dcs_site_file = dcs_conf_dir + '/dcs-site.xml'
    rest_site_file = '%s/rest-%s/conf/rest-site.xml' % (traf_home, traf_ver)
    trafci_file = traf_home + '/trafci/bin/trafci'
    sqenv_file = traf_home + '/sqenvcom.sh'

    ### dcs setting ###
    # servers
    nodes = dbcfgs['node_list'].split(',')
    dcs_cnt = dbcfgs['dcs_cnt_per_node']
    dcs_servers = ''
    for node in nodes:
        dcs_servers += '%s %s\n' % (node, dcs_cnt)

    write_file(dcs_srv_file, dcs_servers)

    ### modify dcs config files ###
    # modify master
    dcs_master = nodes[0]
    append_file(dcs_master_file, dcs_master)

    # modify sqenvcom.sh
    append_file(sqenv_file, dcs_install_env)
    append_file(sqenv_file, rest_install_env)

    # modify dcs-env.sh
    mod_file(dcs_env_file, {'.*DCS_MANAGES_ZK=.*':'export DCS_MANAGES_ZK=false'})

    ports = ParseInI(DEF_PORT_FILE, 'ports').load()
    dcs_master_port = ports['dcs_master_port']
    # modify trafci
    mod_file(trafci_file, {'HNAME=.*':'HNAME=%s:%s' % (dcs_master, dcs_master_port)})

    # modify dcs-site.xml
    net_interface = run_cmd('ip route |grep default|awk \'{print $5}\'')
    hb = ParseXML(hbase_xml_file)
    zk_hosts = hb.get_property('hbase.zookeeper.quorum')
    zk_port = hb.get_property('hbase.zookeeper.property.clientPort')

    p = ParseXML(dcs_site_file)
    p.add_property('dcs.zookeeper.property.clientPort', zk_port)
    p.add_property('dcs.zookeeper.quorum', zk_hosts)
    p.add_property('dcs.dns.interface', net_interface)

    if dbcfgs['dcs_ha'] == 'Y':
        dcs_floating_ip = dbcfgs['dcs_floating_ip']
        dcs_backup_nodes = dbcfgs['dcs_backup_nodes']
        p.add_property('dcs.master.floating.ip', 'true')
        p.add_property('dcs.master.floating.ip.external.interface', net_interface)
        p.add_property('dcs.master.floating.ip.external.ip.address', dcs_floating_ip)
        p.rm_property('dcs.dns.interface')

        # modify trafci to use dcs floating ip instead of dcs master node
        mod_file(trafci_file, {'HNAME=.*':'HNAME=%s:%s' % (dcs_floating_ip, dcs_master_port)})

        # modify backup_master
        for dcs_backup_node in dcs_backup_nodes.split(','):
            append_file(dcs_bkmaster_file, dcs_backup_node)

    p.write_xml()

    ### rest setting ###
    p = ParseXML(rest_site_file)
    p.add_property('rest.zookeeper.property.clientPort', zk_port)
    p.add_property('rest.zookeeper.quorum', zk_hosts)
    p.write_xml()

    ### run sqcertgen ###
    run_cmd('sqcertgen')

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
