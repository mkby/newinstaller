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
import json
from common import *

def run():
    dbcfgs = json.loads(dbcfgs_json)

    TRAF_HOME = cmd_output('cat /etc/default/useradd |grep HOME |cut -d "=" -f 2').strip()
    TRAF_USER = dbcfgs['traf_user']
    SQ_ROOT = '%s/%s/%s-%s' % (TRAF_HOME, TRAF_USER, dbcfgs['traf_basename'], dbcfgs['traf_version'])

    TRAF_VER = dbcfgs['traf_version']
    DISTRO = dbcfgs['distro']
    HBASE_XML_FILE = dbcfgs['hbase_xml_file']
    TRAF_LIB_PATH = SQ_ROOT + '/export/lib'
    SCRATCH_LOCS = dbcfgs['scratch_locs'].split(',')

    DCS_INSTALL_ENV = 'export DCS_INSTALL_DIR=%s/dcs-%s' % (SQ_ROOT, TRAF_VER)
    REST_INSTALL_ENV = 'export REST_INSTALL_DIR=%s/rest-%s' % (SQ_ROOT, TRAF_VER)

    DCS_CONF_DIR = '%s/dcs-%s/conf' % (SQ_ROOT, TRAF_VER)
    DCS_SRV_FILE = DCS_CONF_DIR + '/servers'
    DCS_MASTER_FILE = DCS_CONF_DIR + '/master'
    DCS_BKMASTER_FILE = DCS_CONF_DIR + '/backup-masters'
    DCS_ENV_FILE = DCS_CONF_DIR + '/dcs-env.sh'
    DCS_SITE_FILE = DCS_CONF_DIR + '/dcs-site.xml'
    REST_SITE_FILE = '%s/rest-%s/conf/rest-site.xml' % (SQ_ROOT, TRAF_VER)
    TRAFCI_FILE =  SQ_ROOT + '/trafci/bin/trafci' 
    SQENV_FILE = SQ_ROOT + '/sqenvcom.sh'

    ### kernel settings ###
    run_cmd('sysctl -w kernel.pid_max=65535 2>&1 > /dev/null')
    run_cmd('echo "kernel.pid_max=65535" >> /etc/sysctl.conf')

    # set permission for scratch file dir
    for loc in SCRATCH_LOCS: run_cmd('chmod 777 %s' % loc)

    ### copy jar files ###
    hbase_lib_path = '/usr/lib/hbase/lib'
    if 'CDH' in DISTRO: 
        parcel_lib = '/opt/cloudera/parcels/CDH/lib/hbase/lib'
        if os.path.exists(parcel_lib): hbase_lib_path =  parcel_lib
    elif 'HDP' in DISTRO:
        hbase_lib_path = '/usr/hdp/current/hbase-regionserver/lib'
    elif 'APACHE' in DISTRO:
        hbase_home = dbcfgs['hbase_home']
        hbase_lib_path = hbase_home + '/lib'
        # for apache distro, get hbase version from cmdline
        hbase_ver = cmd_output('%s/bin/hbase version | head -n1' % hbase_home)
        hbase_ver = re.search('HBase (\d\.\d)', hbase_ver).groups()[0]
        DISTRO += hbase_ver

    distro, v1, v2 = re.search('(\w+)(\d)\.(\d)', DISTRO).groups()
    hbase_trx_jar = '%s/hbase-trx-%s%s_%s-%s.jar' % (TRAF_LIB_PATH, distro.lower(), v1, v2, TRAF_VER)
    if not os.path.exists(hbase_trx_jar):
        err('Cannot find hbase trx jar file \'%s\'' % hbase_trx_jar)

    # remove old trx and trafodion-utility jar files
    run_cmd('rm -rf %s/{hbase-trx-*,trafodion-utility-*}' % hbase_lib_path)

    # copy new ones
    run_cmd('cp %s %s' % (hbase_trx_jar, hbase_lib_path))
    run_cmd('cp %s/trafodion-utility-* %s' % (TRAF_LIB_PATH, hbase_lib_path))

    # set permission
    run_cmd('chmod +r %s/{hbase-trx-*,trafodion-utility-*}' % hbase_lib_path)

    ### dcs setting ###
    # servers
    nodes = dbcfgs['node_list'].split(',')
    dcs_cnt = dbcfgs['dcs_cnt_per_node']
    dcs_servers = ''
    for node in nodes:
        dcs_servers += '%s %s\n' % (node, dcs_cnt)

    write_file(DCS_SRV_FILE, dcs_servers)

    # master
    dcs_master = nodes[0]
    append_file(DCS_MASTER_FILE, dcs_master)

    # sqenvcom.sh
    append_file(SQENV_FILE, DCS_INSTALL_ENV)
    append_file(SQENV_FILE, REST_INSTALL_ENV)

    # modify dcs-env.sh
    mod_file(DCS_ENV_FILE, {'.*DCS_MANAGES_ZK=.*':'export DCS_MANAGES_ZK=false'})

    # dcs-site.xml
    net_interface = cmd_output('netstat -rn | grep "^0.0.0.0" | awk \'{print $8}\'').strip()
    hb = ParseXML(HBASE_XML_FILE)
    zk_hosts = hb.get_property('hbase.zookeeper.quorum')
    zk_port = hb.get_property('hbase.zookeeper.property.clientPort')

    p = ParseXML(DCS_SITE_FILE)
    p.add_property('dcs.zookeeper.property.clientPort', zk_port)
    p.add_property('dcs.zookeeper.quorum', zk_hosts)
    p.add_property('dcs.dns.interface', net_interface)

    if dbcfgs['dcs_ha'] == 'yes':
        dcs_floating_ip = dbcfgs['dcs_floating_ip']
        dcs_backup_nodes = dbcfgs['dcs_backup_nodes']
        p.add_property('dcs.master.floating.ip', 'true')
        p.add_property('dcs.master.floating.ip.external.interface', net_interface)
        p.add_property('dcs.master.floating.ip.external.ip.address', dcs_floating_ip)
        p.rm_property('dcs.dns.interface')

        # backup_master
        write_file(DCS_BKMASTER_FILE, dcs_backup_nodes)

        # trafci
        mod_file(TRAFCI_FILE, {'HNAME=.*':'HNAME=%s:23400' % dcs_master})

    p.write_xml()

    ### rest setting ###
    p = ParseXML(REST_SITE_FILE)
    p.add_property('rest.zookeeper.property.clientPort', zk_port)
    p.add_property('rest.zookeeper.quorum', zk_hosts)
    p.write_xml()


# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
