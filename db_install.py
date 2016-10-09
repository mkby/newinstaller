#!/usr/bin/env python
# -*- coding: utf8 -*-

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

import sys
reload(sys)
sys.setdefaultencoding("utf-8")
import os
import re
import socket
import json
import base64
import getpass
import time
from optparse import OptionParser
from glob import glob
from collections import defaultdict
try:
    from prettytable import PrettyTable
except ImportError:
    print 'Python module prettytable is not found. Install python-prettytable first.'
    exit(1)
from common import *

# init global cfgs for user input
cfgs = defaultdict(str)

class HadoopDiscover:
    ''' discover for hadoop related info '''
    def __init__(self, distro, cluster_name, hdfs_srv_name, hbase_srv_name):
        self.rsnodes = []
        self.users = {}
        self.distro = distro
        self.hdfs_srv_name = hdfs_srv_name
        self.hbase_srv_name = hbase_srv_name
        #self.hg = ParseHttp(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']))
        self.hg = ParseHttp(cfgs['mgr_user'], cfgs['mgr_pwd'])
        self.cluster_name = cluster_name
        self.cluster_url = '%s/api/v1/clusters/%s' % (cfgs['mgr_url'], cluster_name.replace(' ', '%20'))
        self._check_version()

    def _check_version(self):
        version = Version()
        if 'CDH' in self.distro: version_list = version.get_version('cdh')
        if 'HDP' in self.distro: version_list = version.get_version('hdp')

        has_version = 0
        for ver in version_list:
            if ver in self.distro: has_version = 1

        if not has_version:
            log_err('Sorry, currently EsgynDB doesn\'t support %s version' % self.distro)

    def get_hadoop_users(self):
        if 'CDH' in self.distro:
            self._get_cdh_users()
        elif 'HDP' in self.distro or 'BigInsights' in self.distro:
            self._get_hdp_users()
        return self.users

    def _get_hdp_users(self):
        desired_cfg = self.hg.get('%s/?fields=Clusters/desired_configs' % (self.cluster_url))
        config_type = {'hbase-env':'hbase_user', 'hadoop-env':'hdfs_user'}
        for k,v in config_type.items():
            desired_tag = desired_cfg['Clusters']['desired_configs'][k]['tag']
            current_cfg = self.hg.get('%s/configurations?type=%s&tag=%s' % (self.cluster_url, k, desired_tag))
            self.users[v] = current_cfg['items'][0]['properties'][v]

    def _get_cdh_users(self):
        def _get_username(service_name, hadoop_type):
            cfg = self.hg.get('%s/services/%s/config' % (self.cluster_url, service_name))
            if cfg.has_key('items'):
                for item in cfg['items']:
                    if item['name'] == 'process_username':
                        return item['value']
            return hadoop_type

        hdfs_user = _get_username(self.hdfs_srv_name, 'hdfs')
        hbase_user = _get_username(self.hbase_srv_name, 'hbase')

        self.users = {'hbase_user':hbase_user, 'hdfs_user':hdfs_user}

    def get_rsnodes(self):
        if 'CDH' in self.distro:
            self._get_rsnodes_cdh()
        elif 'HDP' in self.distro or 'BigInsights' in self.distro:
            self._get_rsnodes_hdp()

        self.rsnodes.sort()
        # use short hostname
        try:
            self.rsnodes = [re.match(r'([\w\-]+).*',n).group(1) for n in self.rsnodes]
        except AttributeError:
            pass
        return self.rsnodes

    def _get_rsnodes_cdh(self):
        """ get list of HBase RegionServer nodes in CDH """
        cm = self.hg.get('%s/api/v6/cm/deployment' % cfgs['mgr_url'])

        hostids = []
        for c in cm['clusters']:
            if c['displayName'] == self.cluster_name:
                for s in c['services']:
                    if s['type'] == 'HBASE':
                        for r in s['roles']:
                            if r['type'] == 'REGIONSERVER': hostids.append(r['hostRef']['hostId'])
        for i in hostids:
            for h in cm['hosts']:
                if i == h['hostId']: self.rsnodes.append(h['hostname'])

    def _get_rsnodes_hdp(self):
        """ get list of HBase RegionServer nodes in HDP """
        hdp = self.hg.get('%s/services/HBASE/components/HBASE_REGIONSERVER' % self.cluster_url )
        self.rsnodes = [ c['HostRoles']['host_name'] for c in hdp['host_components'] ]


class UserInput:
    def __init__(self):
        self.in_data = ParseJson(USER_PROMPT_FILE).load()

    def _basic_check(self, name, answer):
        isYN = self.in_data[name].has_key('isYN')
        isdigit = self.in_data[name].has_key('isdigit')
        isexist = self.in_data[name].has_key('isexist')
        isIP = self.in_data[name].has_key('isIP')
        isuser = self.in_data[name].has_key('isuser')

        # check answer value basicly
        answer = answer.rstrip()
        if answer:
            if isYN:
                answer = answer.upper()
                if answer != 'Y' and answer != 'N':
                    log_err('Invalid parameter for %s, should be \'Y|y|N|n\'' % name)
            elif isdigit:
                if not answer.isdigit():
                    log_err('Invalid parameter for %s, should be a number' % name)
            elif isexist:
                if not os.path.exists(answer):
                    log_err('%s path \'%s\' doesn\'t exist' % (name, answer))
            elif isIP:
                try:
                    socket.inet_pton(socket.AF_INET, answer)
                except:
                    log_err('Invalid IP address \'%s\'' % answer)
            elif isuser:
                if re.match(r'\w+', answer).group() != answer:
                    log_err('Invalid user name \'%s\'' % answer)

        else:
            log_err('Empty value for \'%s\'' % name)

    def _handle_prompt(self, name, user_defined):
        prompt = self.in_data[name]['prompt']
        default = user_defined

        if (not default) and self.in_data[name].has_key('default'):
            default = self.in_data[name]['default']

        ispasswd = self.in_data[name].has_key('ispasswd')
        isYN = self.in_data[name].has_key('isYN')

        # no default value for password
        if ispasswd: default = ''

        if isYN:
            prompt = prompt + ' (Y/N) '

        if default:
            prompt = prompt + ' [' + default + ']: '
        else:
            prompt = prompt + ': '

        # no default value for password
        if ispasswd:
            orig = getpass.getpass(prompt)
            confirm = getpass.getpass('Confirm ' + prompt)
            if orig == confirm:
                #answer = base64.b64encode(confirm)
                answer = confirm
            else:
                log_err('Password mismatch')
        else:
            try:
                answer = raw_input(prompt)
            except UnicodeEncodeError:
                log_err('Character Encode error, check user input')
            if not answer and default: answer = default

        return answer

    def get_input(self, name, user_defined='', prompt_mode=True):
        if self.in_data.has_key(name):
            if prompt_mode:
                # save configs to global dict
                cfgs[name] = self._handle_prompt(name, user_defined)

            # check basic values from global configs
            self._basic_check(name, cfgs[name])
        else:
            # should not go to here, just in case
            log_err('Invalid prompt')

    def get_confirm(self):
        answer = raw_input('Confirm result (Y/N) [N]: ')
        if not answer: answer = 'N'

        answer = answer.upper()
        if answer != 'Y' and answer != 'N':
            log_err('Invalid parameter, should be \'Y|y|N|n\'')
        return answer

    def notify_user(self):
        """ show the final configs to user """
        format_output('Final Configs')
        title = ['config type', 'value']
        pt = PrettyTable(title)
        for item in title:
            pt.align[item] = 'l'

        for key,value in sorted(cfgs.items()):
            if self.in_data.has_key(key) and value:
        #        if self.in_data[k].has_key('ispasswd'): continue
                pt.add_row([key, value])
        print pt
        confirm = self.get_confirm()
        if confirm != 'Y':
            if os.path.exists(DBCFG_FILE): os.remove(DBCFG_FILE)
            log_err('User quit')


def log_err(errtext):
    # save tmp config files
    tp = ParseInI(DBCFG_TMP_FILE)
    tp.save(cfgs)

    err_m(errtext)


def get_cluster_cfgs(cfgs):
    if cfgs['distro'] == 'APACHE': return
    #hg = ParseHttp(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']))
    hg = ParseHttp(cfgs['mgr_user'], cfgs['mgr_pwd'])
    validate_url_v1 = '%s/api/v1/clusters' % cfgs['mgr_url']
    validate_url_v6 = '%s/api/v6/clusters' % cfgs['mgr_url']
    content = hg.get(validate_url_v1)

    if content['items'][0].has_key('name'):
        # use v6 rest api for CDH to get fullversion
        content = hg.get(validate_url_v6)

    cluster_cfgs = []
    # loop all managed clusters
    for clusters in content['items']:
        try:
            # HDP
            distro = clusters['Clusters']['version']
            cluster_name = clusters['Clusters']['cluster_name']
        except KeyError:
            # CDH
            try:
                distro = 'CDH' + clusters['fullVersion']
                cluster_name = clusters['displayName']
            except KeyError:
                distro = cluster_name = ''

        cluster_cfgs.append([distro, cluster_name])

    return cluster_cfgs


def user_input(apache_hadoop=False, offline=False, prompt_mode=True):
    """ get user's input and check input value """
    global cfgs
    # load from temp config file if in prompt mode
    if os.path.exists(DBCFG_TMP_FILE) and prompt_mode == True:
        tp = ParseInI(DBCFG_TMP_FILE)
        cfgs = tp.load()

    u = UserInput()
    g = lambda n: u.get_input(n, cfgs[n], prompt_mode=prompt_mode)

    g('java_home')

    if offline:
        g('local_repo_dir')
        if not glob('%s/repodata' % cfgs['local_repo_dir']):
            log_err('repodata directory not found, this is not a valid repository directory')
        cfgs['offline_mode'] = 'Y'
        cfgs['repo_ip'] = socket.gethostbyname(socket.gethostname())
        cfgs['repo_port'] = '9900'

    pkg_list = ['trafodion', 'esgynDB']
    # find tar in installer folder, if more than one found, use the first one
    for pkg in pkg_list:
        tar_loc = glob('%s/%s*.tar.gz' % (INSTALLER_LOC, pkg))
        if tar_loc:
            cfgs['traf_package'] = tar_loc[0]
            break

    g('traf_package')

    # get basename and version from tar filename
    try:
        pattern = '|'.join(pkg_list)
        cfgs['traf_basename'], cfgs['traf_version'] = re.search(r'(.*%s.*)-(\d\.\d\.\d).*' % pattern, cfgs['traf_package']).groups()
    except:
        log_err('Invalid package tar file')

    if float(cfgs['traf_version'][:3]) >= 2.2:
        cfgs['req_java8'] = 'Y'
    else:
        cfgs['req_java8'] = 'N'


    if apache_hadoop:
        g('hadoop_home')
        g('hbase_home')
        g('hive_home')
        g('hdfs_user')
        g('hbase_user')
        g('first_rsnode')
        cfgs['distro'] = 'APACHE'
    else:
        g('mgr_url')
        if not ('http:' in cfgs['mgr_url'] or 'https:' in cfgs['mgr_url']):
            cfgs['mgr_url'] = 'http://' + cfgs['mgr_url']

        g('mgr_user')
        g('mgr_pwd')

        cluster_cfgs = get_cluster_cfgs(cfgs)
        c_index = 0
        # support multiple clusters, test on CDH only
        if len(cluster_cfgs) > 1:
            for index, config in enumerate(cluster_cfgs):
                print str(index + 1) + '. ' + config[1]
            g('cluster_no')
            c_index = int(cfgs['cluster_no']) - 1
            if c_index < 0 or c_index >= len(cluster_cfgs):
                log_err('Incorrect number')

        # cdh uses different service names in multiple clusters
        if c_index == 0:
            cfgs['hbase_service_name'] = 'hbase'
            cfgs['hdfs_service_name'] = 'hdfs'
            cfgs['zookeeper_service_name'] = 'zookeeper'
        else:
            cfgs['hbase_service_name'] = 'hbase' + str(c_index+1)
            cfgs['hdfs_service_name'] = 'hdfs' + str(c_index+1)
            cfgs['zookeeper_service_name'] = 'zookeeper' + str(c_index+1)

        distro, cluster_name = cluster_cfgs[c_index]
        discover = HadoopDiscover(distro, cluster_name, cfgs['hdfs_service_name'], cfgs['hbase_service_name'])
        rsnodes = discover.get_rsnodes()
        hadoop_users = discover.get_hadoop_users()

        cfgs['distro'] = distro
        cfgs['cluster_name'] = cluster_name.replace(' ', '%20')
        cfgs['hdfs_user'] = hadoop_users['hdfs_user']
        cfgs['hbase_user'] = hadoop_users['hbase_user']
        cfgs['first_rsnode'] = rsnodes[0] # first regionserver node

    # manually set node list in apache hadoop
    if apache_hadoop:
        cfgs['use_data_node'] = 'N'
    else:
        g('use_data_node')

    if cfgs['use_data_node'].upper() == 'N':
        g('node_list')
        node_lists = expNumRe(cfgs['node_list'])

        # check if node list is expanded successfully
        if len([1 for node in node_lists if '[' in node]):
            log_err('Failed to expand node list, please check your input.')

        # check node list should be part of HBase RS nodes, no check for apache hadoop
        if not apache_hadoop and set(node_lists).difference(set(rsnodes)):
            log_err('Incorrect node list, should be part of RegionServer nodes')

        cfgs['node_list'] =  ','.join(node_lists)
    else:
        cfgs['node_list'] = ','.join(rsnodes)

    # check node connection
    for node in cfgs['node_list'].split(','):
        rc = os.system('ping -c 1 %s >/dev/null 2>&1' % node)
        if rc: log_err('Cannot ping %s, please check network connection and /etc/hosts' % node)

    g('traf_pwd')
    g('dcs_cnt_per_node')
    g('scratch_locs')
    g('traf_start')

    # TODO add kerberos

    # ldap security
    g('ldap_security')
    if cfgs['ldap_security'].upper() == 'Y':
        g('db_root_user')
        g('db_admin_user')
        g('db_admin_pwd')
        g('ldap_hosts')
        g('ldap_port')
        g('ldap_identifiers')
        g('ldap_encrypt')
        if  cfgs['ldap_encrypt'] == '1' or cfgs['ldap_encrypt'] == '2':
            g('ldap_certpath')
        elif cfgs['ldap_encrypt'] == '0':
            cfgs['ldap_certpath'] = ''
        else:
            log_err('Invalid ldap encryption level')

        g('ldap_userinfo')
        if cfgs['ldap_userinfo'] == 'Y':
            g('ldap_user')
            g('ldap_pwd')
        else:
            cfgs['ldap_user'] = ''
            cfgs['ldap_pwd'] = ''

    # DCS HA
    g('dcs_ha')
    if cfgs['dcs_ha'].upper() == 'Y':
        g('dcs_floating_ip')
        g('dcs_interface')
        g('dcs_backup_nodes')
        # check dcs backup nodes should exist in node list
        if sorted(list(set((cfgs['dcs_backup_nodes'] + ',' + cfgs['node_list']).split(',')))) != sorted(cfgs['node_list'].split(',')):
            log_err('Invalid DCS backup nodes, please pick up from node list')

    # set other config to cfgs
    if apache_hadoop:
        cfgs['hbase_xml_file'] = cfgs['hbase_home'] + '/conf/hbase-site.xml'
        cfgs['hdfs_xml_file'] = cfgs['hadoop_home'] + '/etc/hadoop/hdfs-site.xml'
    else:
        cfgs['hbase_xml_file'] = '/etc/hbase/conf/hbase-site.xml'

    cfgs['traf_user'] = 'trafodion'
    cfgs['config_created_date'] = time.strftime('%Y/%m/%d %H:%M %Z')

    u.notify_user()


def get_options():
    usage = 'usage: %prog [options]\n'
    usage += '  Trafodion install main script.'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config-file", dest="cfgfile", metavar="FILE",
                help="Json format file. If provided, all install prompts \
                      will be taken from this file and not prompted for.")
    parser.add_option("-u", "--remote-user", dest="user", metavar="USER",
                help="Specify ssh login user for remote server, \
                      if not provided, use current login user as default.")
    parser.add_option("--ansible", action="store_true", dest="ansible", default=False,
                help="Call ansible to install.")
    parser.add_option("-b", "--become-method", dest="method", metavar="METHOD",
                help="Specify become root method for ansible [ sudo | su | pbrun | pfexec | runas | doas ].")
    parser.add_option("-f", "--fork", dest="fork", metavar="FORK",
                help="Specify number of parallel processes to run sub scripts (default=10)" )
    parser.add_option("--no-passwd", action="store_true", dest="pwd", default=True,
                help="Not Prompt SSH login password for remote hosts. \
                      If set, passwordless ssh is required.")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                help="Verbose mode, will print commands.")
    parser.add_option("--build", action="store_true", dest="build", default=False,
                help="Build the config file in guided mode only.")
    parser.add_option("--upgrade", action="store_true", dest="upgrade", default=False,
                help="Upgrade install, it is useful when reinstalling Trafodion.")
    parser.add_option("--apache-hadoop", action="store_true", dest="apache", default=False,
                help="Install Trafodion on top of Apache Hadoop.")
    parser.add_option("--offline", action="store_true", dest="offline", default=False,
                help="Enable local repository for offline installing Trafodion.")
    parser.add_option("--version", action="store_true", dest="version", default=False,
                help="Show the installer version.")

    (options, args) = parser.parse_args()
    return options

def main():
    """ db_installer main loop """
    global cfgs

    format_output('Trafodion Installation ToolKit')

    # handle parser option
    options = get_options()
    if options.ansible:
        from ans_wrapper import run
    else:
        from py_wrapper import run

    if not options.ansible:
        if options.method: log_err('Wrong parameter, cannot specify ansible option without ansible enabled')

    if options.version: version()
    if options.build and options.cfgfile:
        log_err('Wrong parameter, cannot specify both --build and --config-file')

    if options.build and options.offline:
        log_err('Wrong parameter, cannot specify both --build and --offline')


    if options.method:
        if options.method not in ['sudo','su','pbrun','pfexec','runas','doas']:
            log_err('Wrong method, valid methods: [ sudo | su | pbrun | pfexec | runas | doas ].')

    if options.cfgfile:
        if not os.path.exists(options.cfgfile):
            log_err('Cannot find config file \'%s\'' % options.cfgfile)
        config_file = options.cfgfile
    else:
        config_file = DBCFG_FILE


    # not specified config file and default config file doesn't exist either
    p = ParseInI(config_file)
    if options.build or (not os.path.exists(config_file)):
        if options.build: format_output('DryRun Start')
        user_input(options.apache, options.offline, prompt_mode=True)

        # save config file as json format
        print '\n** Generating config file to save configs ... \n'
        p.save(cfgs)

    # config file exists
    else:
        print '\n** Loading configs from config file ... \n'
        cfgs = p.load()
        if options.offline and cfgs['offline_mode'] != 'Y':
            log_err('To enable offline mode, must set "offline_mode = Y" in config file')
        user_input(options.apache, options.offline, prompt_mode=False)

    if options.offline:
        http_start(cfgs['local_repo_dir'], cfgs['repo_port'])
    else:
        cfgs['offline_mode'] = 'N'


    if not options.build:
        format_output('Installation Start')

        ### perform actual installation ###
        run(cfgs, options)

        format_output('Installation Complete')

        if options.offline: http_stop()

        # rename default config file when successfully installed
        # so next time user can input new variables for a new install
        # or specify the backup config file to install again
        try:
            # only rename default config file
            ts = time.strftime('%y%m%d_%H%M')
            if config_file == DBCFG_FILE and os.path.exists(config_file):
                os.rename(config_file, config_file + '.bak' + ts)
        except OSError:
            log_err('Cannot rename config file')
    else:
        format_output('DryRun Complete')

    # remove temp config file
    if os.path.exists(DBCFG_TMP_FILE): os.remove(DBCFG_TMP_FILE)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt,EOFError):
        tp = ParseInI(DBCFG_TMP_FILE)
        tp.save(cfgs)
        http_stop()
        print '\nAborted...'
