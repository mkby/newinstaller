#!/usr/bin/env python

import os
import sys
import socket
import time
import json
import getpass
import glob
import telnetlib
from time import sleep
from collections import defaultdict
from optparse import OptionParser
from random import choice

from cm_api.api_client import ApiResource, ApiException
from cm_api.endpoints.services import ApiServiceSetupInfo
from scripts import wrapper
from scripts.common import err_m, info, ok, http_start, http_stop, Remote, \
                           retry, expNumRe, ParseInI, DEF_PORT_FILE, CONFIG_DIR

CM_PORT = 7180

class DeployCDH(object):
    def __init__(self, cdh_hosts, roles, cm_port, cm_user='admin', cm_passwd='admin', cluster_name='cluster1'):

        self.cluster_name = cluster_name
        self.cm_port = cm_port
        self.cdh_version = "CDH5"

        self.cdh_hosts = cdh_hosts
        self.roles = roles

        self._get_host_allocate()
        self.cm_host = self.cdh_hosts[0]

        self.api = ApiResource(self.cm_host, self.cm_port, cm_user, cm_passwd, version=7)
        self.cm = self.api.get_cloudera_manager()

        try:
            self.cluster = self.api.get_cluster(self.cluster_name)
        except:
            try:
                self.cluster = self.api.create_cluster(self.cluster_name, self.cdh_version)
            except:
                err_m('Cannot connect to cloudera manager on %s' % self.cm_host)

        # add all our hosts to the cluster
        try:
            self.cluster.add_hosts(self.cdh_hosts)
            info('Add hosts successfully')
        except Exception as e:
            if e.code == 400:
                info('Already Added hosts')
            elif e.code == 404:
                err_m(e.message)


    def _auto_allocate(self, hosts):
        # enable mgmt node if node count is larger than mgmt_th
        mgmt_th = 6

        if type(hosts) != list: err_m('hosts parameter should be a list')
        host_num = len(hosts)
        # node<=3, ZK=1 ,node>3, ZK=3
        zk_num = 1 if host_num <= 3 else 3

        # with mgmt node
        if host_num >= mgmt_th:
            self.ap_host = self.es_host = self.ho_host = self.sm_host = self.nn_host = self.hm_host = self.jt_host = hosts[0]
            self.dn_hosts = self.rs_hosts = self.tt_hosts = hosts[1:]
            self.snn_host = hosts[1]
            self.hms_host = hosts[2]
            self.hs2_host = hosts[3]
        # without mgmt node
        else:
            if host_num == 1:
                self.ap_host = self.es_host = self.ho_host = self.sm_host = self.jt_host = \
                self.nn_host = self.hm_host = self.snn_host = self.hms_host = self.hs2_host = hosts[0]
            elif host_num > 1:
                # nn, snn not on same node
                tmp_hosts = hosts[:]
                self.nn_host = choice(tmp_hosts)
                tmp_hosts.remove(self.nn_host)
                self.snn_host = choice(tmp_hosts)
                self.hm_host = choice(tmp_hosts)
                self.jt_host = choice(hosts)
                self.hms_host = choice(hosts)
                self.hs2_host = choice(hosts)
                # cm
                self.ap_host = choice(hosts)
                self.es_host = choice(hosts)
                self.ho_host = choice(hosts)
                self.sm_host = choice(hosts)

            self.dn_hosts = self.rs_hosts = self.tt_hosts = hosts

        self.zk_hosts = hosts[-zk_num:]

    def _get_host_allocate(self):
        # auto set if no role config found
        if not self.roles:
            self._auto_allocate(self.cdh_hosts)
            return

        valid_roles = ['DN', 'RS', 'ZK', 'HM', 'NN', 'SNN', 'AP', 'ES', 'SM', 'HO', 'TT', 'JT', 'HMS', 'HS2']
        role_host = defaultdict(list)

        # roles is a dict
        items = [[h, r.split(',')] for h, r in self.roles.iteritems()]
        for item in items:
            for role in item[1]:
                role = role.strip()
                if role not in valid_roles: err_m('Incorrect role config')
                role_host[role].append(item[0])

        # cdh
        self.nn_host = role_host['NN'][0]
        self.snn_host = role_host['SNN'][0]
        self.hm_host = role_host['HM'][0]
        self.jt_host = role_host['JT'][0]
        self.hms_host = role_host['HMS'][0]
        self.hs2_host = role_host['HS2'][0]
        self.tt_hosts = role_host['TT']
        self.zk_hosts = role_host['ZK']
        self.dn_hosts = role_host['DN']
        self.rs_hosts = role_host['RS']
        # cm
        self.ap_host = role_host['AP'][0]
        self.es_host = role_host['ES'][0]
        self.ho_host = role_host['HO'][0]
        self.sm_host = role_host['SM'][0]

    def setup_cms(self):
        try:
            self.cm.delete_mgmt_service()
        except:
            pass

        # create the management service
        try:
            mgmt = self.cm.create_mgmt_service(ApiServiceSetupInfo())
            mgmt.create_role('AlertPublisher', "ALERTPUBLISHER", self.ap_host)
            mgmt.create_role('EventServer', "EVENTSERVER", self.es_host)
            mgmt.create_role('HostMonitor', "HOSTMONITOR", self.hm_host)
            mgmt.create_role('ServiceMonitor', "SERVICEMONITOR", self.sm_host)
            ok('Cloudera management service created successfully.')
        except ApiException:
            info('Cloudera management service had already been created.')

    def setup_parcel(self):
        parcels_list = []
        i = 1
        for p in self.cluster.get_all_parcels():
            if p.stage == 'AVAILABLE_REMOTELY': continue
            elif p.stage == 'ACTIVATED':
                info('Parcel [%s] has already been activated' % p.version)
                return
            else:
                print '\t' + str(i) + ': ' + p.product + ' ' + p.version
                i += 1
                parcels_list.append(p)

        if len(parcels_list) == 0:
            err_m('No downloaded ' + self.cdh_version + ' parcel found!')
        elif len(parcels_list) > 1:
            index = raw_input('Input parcel number:')
            if not index.isdigit:
                err_m('Error index, must be a number')
            cdh_parcel = parcels_list[int(index)-1]
        else:
            cdh_parcel = parcels_list[0]

      #  # download the parcel
      #  print "Starting parcel download. This might take a while."
      #  cmd = cdh_parcel.start_download()
      #  if cmd.success != True:
      #      print "Parcel download failed!"
      #      exit(0)

      #  # make sure the download finishes
      #  while cdh_parcel.stage != 'DOWNLOADED':
      #  sleep(5)
      #      cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

      #  print cdh_parcel.product + ' ' + cdh_parcel.version + " downloaded"

        # distribute the parcel
        info('Starting parcel distribution. This might take a while.')
        cmd = cdh_parcel.start_distribution()
        i = 0
        while cmd.success == None:
            i += 1
            sleep(5)
            cmd = cmd.fetch()
            s = '.' * i
            print '\r%s' % s,
            sys.stdout.flush()
        if cmd.success != True:
            err_m('Parcel distribution failed!')

        # make sure the distribution finishes
        while cdh_parcel.stage != "DISTRIBUTED":
            sleep(5)
            cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

        ok(cdh_parcel.product + ' ' + cdh_parcel.version + ' distributed')

        # activate the parcel
        cmd = cdh_parcel.activate()
        if cmd.success != True:
            err_m('Parcel activation failed!')

        # make sure the activation finishes
        while cdh_parcel.stage != "ACTIVATED":
            sleep(5)
            cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

        ok(cdh_parcel.product + ' ' + cdh_parcel.version + ' activated')

    def _create_service(self, sdata):
        try:
            self.cluster.get_service(sdata['sname'])
            info('Service %s had already been configured' % sdata['sname'])
        except ApiException:
            service = self.cluster.create_service(sdata['sname'], sdata['stype'])
            ok('Service %s had been created successfully' % sdata['sname'])
            for role in sdata['roles']:
                if role.has_key('rhost'):
                    service.create_role(role['rname'], role['rtype'], role['rhost'])
                elif role.has_key('rhosts'):
                    rid = 0
                    for host in role['rhosts']:
                        rid += 1
                        service.create_role(role['rname'] + '-' + str(rid), role['rtype'], host)

    def setup_cdh(self):
        service_data = [ { 'sname': 'hdfs', 'stype': 'HDFS',
                           'roles': [ {'rname': 'hdfs-namenode', 'rtype': 'NAMENODE', 'rhost': self.nn_host},
                                      {'rname': 'hdfs-secondarynamenode', 'rtype': 'SECONDARYNAMENODE', 'rhost': self.snn_host},
                                      {'rname': 'hdfs-datanode', 'rtype': 'DATANODE', 'rhosts': self.dn_hosts} ]
                         },
                         { 'sname': 'zookeeper', 'stype': 'ZOOKEEPER',
                           'roles': [ {'rname': 'zookeeper', 'rtype': 'SERVER', 'rhosts': self.zk_hosts} ]
                         },
                         { 'sname': 'hbase', 'stype': 'HBASE',
                           'roles': [ {'rname': 'hbase-master', 'rtype': 'MASTER', 'rhost': self.hm_host},
                                      {'rname': 'hdfs-regionserver', 'rtype': 'REGIONSERVER', 'rhosts': self.rs_hosts} ]
                         },
                         { 'sname': 'hive', 'stype': 'HIVE',
                           'roles': [ {'rname': 'hive-metastore', 'rtype': 'HIVEMETASTORE', 'rhost': self.hms_host},
                                      {'rname': 'hive-server2', 'rtype': 'HIVESERVER2', 'rhost': self.hs2_host},
                                      {'rname': 'hive-gateway', 'rtype': 'GATEWAY', 'rhosts': self.dn_hosts} ]
                         },
                         { 'sname': 'mapreduce', 'stype': 'MAPREDUCE',
                           'roles': [ {'rname': 'mapreduce-jobtracker', 'rtype': 'JOBTRACKER', 'rhost': self.jt_host},
                                      {'rname': 'mapreduce-tasktracker', 'rtype': 'TASKTRACKER', 'rhosts': self.tt_hosts} ]
                         }
                      ]

        for sdata in service_data:
            self._create_service(sdata)

        # additional config for hive
        try:
            hive_service = self.cluster.get_service('hive')
            hive_metastore_host = self.cm_host # should be same as cm's host, FQDN
            hive_metastore_name = 'hive'
            hive_metastore_password = 'hive'
            hive_metastore_database_port = '7432'
            hive_metastore_database_type = 'postgresql'
            hive_config = { 'hive_metastore_database_host' : hive_metastore_host, \
                            'hive_metastore_database_name' : hive_metastore_name, \
                            'hive_metastore_database_password' : hive_metastore_password, \
                            'hive_metastore_database_port' : hive_metastore_database_port, \
                            'hive_metastore_database_type' : hive_metastore_database_type }
            hive_service.update_config(hive_config)
            ok('Additional hive configs had been updated')
        except ApiException as e:
            err_m(e.message)

        # use auto configure for *-site.xml configs
        try:
            self.cluster.auto_configure()
        except ApiException as e:
            err_m(e.message)

    def start_cms(self):
        # start the management service
        info('Starting cloudera management service...')
        cms = self.cm.get_service()
        cms.start().wait()
        ok('Cloudera management service started successfully')

    def start_cdh(self):
        info('Excuting first run command. This might take a while.')
        cmd = self.cluster.first_run()

        while cmd.success == None:
            cmd = cmd.fetch()
            sleep(1)

        if cmd.success != True:
            err_m('The first run command failed: ' + cmd.resultMessage)

        ok('First run successfully executed. Your cluster has been set up!')


def deploy_cdh(cdh_hosts, roles):
    # config cdh
    deploy = DeployCDH(cdh_hosts, roles, CM_PORT)
    deploy.setup_cms()
    deploy.setup_parcel()
    deploy.start_cms()
    deploy.setup_cdh()
    deploy.start_cdh()

def get_options():
    usage = 'usage: %prog [options]\n'
    usage += '  Cloudera install script. It will install and configure Cloudera rpms \n\
  and deploy Hadoop services via cm api. Please edit configs/cdh_config.ini before run.'
    parser = OptionParser(usage=usage)
    parser.add_option("-u", "--remote-user", dest="user", metavar="USER",
                help="Specify ssh login user for remote server, \
                      if not provided, use current login user as default.")
    parser.add_option("-p", "--package-only", action="store_true", dest="pkgonly", default=False,
                help="Install Cloudera package only but not deploy it. Please use CM web page to deploy it manually.")
    parser.add_option("--enable-pwd", action="store_true", dest="pwd", default=False,
                help="Prompt SSH login password for remote hosts. \
                      If set, \'sshpass\' tool is required.")

    (options, args) = parser.parse_args()
    return options

def main():
    options = get_options()

    # get configs from file
    CDH_CFG_FILE = CONFIG_DIR + '/cdh_config.ini'
    dirs = ParseInI(CDH_CFG_FILE, 'dirs').load()
    hosts = ParseInI(CDH_CFG_FILE, 'hosts').load()
    ports = ParseInI(DEF_PORT_FILE, 'ports').load()
    roles = ParseInI(DEF_PORT_FILE, 'roles').load()

    repo_dir = dirs['repo_dir']
    parcel_dir = dirs['parcel_dir']
    repo_http_port = ports['repo_http_port']
    cdh_hosts = expNumRe(hosts['hosts'])
    cdhmaster = cdh_hosts[0]

    if not repo_dir: err_m('Failed to get repository dir from %s' % CDH_CFG_FILE)
    if not parcel_dir: err_m('Failed to get parcel dir from %s' % CDH_CFG_FILE)

    with open('/etc/hosts', 'r') as f:
        lines = f.readlines()

    try:
        etc_hosts =[ [l for l in lines if h in l][0] for h in cdh_hosts ]
    except IndexError:
        err_m('hosts mismatch, please check the hosts in config.ini are set in /etc/hosts.')

    hostname = socket.gethostname()
    repo_ip = socket.gethostbyname(hostname)

    cfgs = defaultdict(str)
    cfgs['node_list'] = ','.join(cdh_hosts)
    cfgs['etc_hosts'] = etc_hosts
    cfgs['parcel_dir'] = parcel_dir
    cfgs['repo_ip'] = repo_ip
    cfgs['repo_http_port'] = repo_http_port

    def cdh_install():
        if options.pwd:
            pwd = getpass.getpass('Input remote host SSH Password: ')
        else:
            pwd = ''

        # copy cloudera parcel repo
        info('Copy parcel repo to master nodes')
        remote = Remote(cdhmaster, user='', pwd=pwd)
        remote.execute('sudo mkdir -p /opt/cloudera/parcel-repo/')
        parcel_files = glob.glob(parcel_dir + '/*')
        remote.copy(parcel_files, remote_folder='/tmp')
        for parcel_file in parcel_files:
            remote.execute('sudo mv /tmp/%s /opt/cloudera/parcel-repo/' % parcel_file.split('/')[-1])

        # deploy cloudera
        http_start(repo_dir, repo_http_port)
        wrapper.run(cfgs, options, mode='cloudera', pwd=pwd)
        http_stop()
        ok('Cloudera RPMs installed successfully!')

    cdh_install()

    def telnet_stat():
        try:
            telnetlib.Telnet(cdhmaster, CM_PORT)
            return True
        except:
            return False
    retry(telnet_stat, 20, 5, 'cloudera manager')

    if not options.pkgonly: deploy_cdh(cdh_hosts, roles)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        http_stop()
        print '\nAborted...'
