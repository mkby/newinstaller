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

import os
import time
import json
import getpass
from optparse import OptionParser
from collections import defaultdict
try:
    from prettytable import PrettyTable
except ImportError:
    print 'Python module prettytable is not found. Install python-prettytable first.'
    exit(1)
from scripts.constants import DBCFG_FILE, INSTALLER_LOC, WARN, ERR, OK
from scripts.common import err_m, err, ParseInI, ParseHttp, expNumRe, format_output, HadoopDiscover
from scripts import wrapper

STAT_ERR  = ' x '
STAT_WARN = ' w '
STAT_OK   = ' o '
C_STAT_ERR  = '\33[31m x \33[0m'
C_STAT_WARN = '\33[33m w \33[0m'
C_STAT_OK   = '\33[32m o \33[0m'

CAT_HW = [
'cpu_arch',
'cpu_cores',
'disk_nums',
'user_disk_free',
'install_disk_free',
'mem_total',
'mem_free',
'swap_pct',
'ext_interface',
'net_interfaces',
'net_bw',
]

CAT_CFG = [
'linux_distro',
'kernel_ver',
'hostname',
'fqdn',
'loopback',
'systime',
'timezone',
'ntp_status',
'firewall_status',
'core_pattern',
'pid_max',
'tcp_time',
'tcp_intvl',
'tcp_probes',
'home_nfs',
'sudo',
'network_mgr_status',
'ssh_pam',
'python_ver',
]

CAT_HADOOP = [
'default_java',
'hadoop_auth',
'hadoop_group_mapping',
'hadoop_distro',
'hbase_ver',
'hdfs_ver',
'hive_ver',
]

CAT_TRAF = [
'traf_status',
]

ALL_CATS = {'Hardware':CAT_HW, 'Configs':CAT_CFG, 'Hadoop':CAT_HADOOP, 'Trafodion':CAT_TRAF}
ALL_ITEMS = CAT_HW + CAT_CFG + CAT_HADOOP + CAT_TRAF

def get_options():
    usage = 'usage: %prog [options]\n'
    usage += '  Discovery script.'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config-file", dest="cfgfile", metavar="FILE",
                      help="Json format file. If provided, all install prompts \
                            will be taken from this file and not prompted for.")
    parser.add_option("-l", "--log-file", dest="logfile", metavar="FILE",
                      help="Specify the log file name.")
    parser.add_option("-u", "--remote-user", dest="user", metavar="USER",
                      help="Specify ssh login user for remote server, \
                            if not provided, use current login user as default.")
    parser.add_option("-j", "--json", action="store_true", dest="json", default=False,
                      help="Output result in JSON format.")
    parser.add_option("-a", "--all", action="store_true", dest="all", default=False,
                      help="Display all scan results.")
    parser.add_option("-n", "--net-perf", action="store_true", dest="perf", default=False,
                      help="Run network bandwidth tests.")
    parser.add_option("--enable-pwd", action="store_true", dest="pwd", default=False,
                      help="Prompt SSH login password for remote hosts. \
                            If set, \'sshpass\' tool is required.")
    parser.add_option("-p", "--password", dest="password", metavar="PASSWD",
                      help="Specify ssh login password for remote server.")
    (options, args) = parser.parse_args()
    return options

def overview(results):
    pt_item = []

    for item in ALL_ITEMS:
        doc = results[0][item]['doc']
        expected = results[0][item].get('expected','-')
        sterr = stwarn = stok = stcons = 0
        chk_arr = [] # array for consistent check
        for result in results:
            status = result[item].get('status','')
            consistent = result[item].get('consistent','')
            if consistent == 'true':
                chk_arr.append(result[item]['value'])
                expected = 'Consistent'
            if status == ERR:
                sterr += 1
            elif status == WARN:
                stwarn += 1
            elif status == OK:
                stok += 1

        # check consistency
        if len(list(set(chk_arr))) > 1:
            status = STAT_WARN

        if not status: continue
        if sterr:
            status = STAT_ERR
        elif stwarn:
            status = STAT_WARN
        elif stok:
            status = STAT_OK

        pt_item.append([doc, status, expected])

    pt_title = ['OverView', 'Stat', 'Expected']
    pt = PrettyTable(pt_title)
    for arr in pt_item:
        pt.add_row(arr)

    return str(pt)

def wrap_line(val, length):
    wrap_val = val[:length]
    l_num = len(val) / length + 1
    for l in xrange(1, l_num):
        wrap_val += '\n' + val[l*length:(l+1)*length]

    if val[l_num*length:]:
        wrap_val += '\n' + val[l_num*length:]

    return wrap_val

def detail_view(results):
    pt_title = ['DetailView']
    for index, result in enumerate(results):
        hostname = result['hostname']['value']
        pt_title += [hostname, 'Stat%d' % (index+1)]
    pt_title += ['Expected']

    pt_items = []

    for category, items in ALL_CATS.items():
        line = [' %s %s %s' % ('-'*10, category, '-'*10)]
        line += (len(results)*2+1)*['-----']
        pt_items.append(line)
        for item in items:
            # handle dependencies values seperately
            if item == 'dependencies': continue
            doc = results[0][item]['doc']
            expected = results[0][item].get('expected','-')
            lines = [doc]
            for result in results:
                value = str(result[item]['value'])
                # wrap line for long string
                value = wrap_line(value, 20)

                status = result[item].get('status','-')
                if status == OK:
                    status = STAT_OK
                if status == WARN:
                    status = STAT_WARN
                if status == ERR:
                    status = STAT_ERR

                lines += [value, status]
            lines += [expected]

            pt_items.append(lines)

    pt = PrettyTable(pt_title)
    for arr in pt_items:
        pt.add_row(arr)

    return str(pt)

def dependency_view(results):
    rpms = [(result['hostname']['value'],result['dependencies']['value']) for result in results]

    output = '\n*** EsgynDB RPM Dependencies ***:\n'
    for hostname, rpm in rpms:
        output += 'Host: ' + hostname + '\n'
        output += '-' * 48 + '\n'
        for k,v in rpm.items():
            output += '%20s | %20s' % (k, v) + '\n'
        output += '-' * 48 + '\n'

    return output

def main():
    options = get_options()

    cfgs = defaultdict(str)

    if options.cfgfile:
        if not os.path.exists(options.cfgfile):
            err_m('Cannot find config file \'%s\'' % options.cfgfile)
        config_file = options.cfgfile
    else:
        config_file = DBCFG_FILE

    if options.pwd:
        if options.password:
            pwd = options.password
        else:
            pwd = getpass.getpass('Input remote host SSH Password: ')
    else:
        pwd = ''

    if os.path.exists(config_file):
        cfgs = ParseInI(config_file, 'dbconfigs').load()
        if cfgs['mgr_url']:
            if not ('http:' in cfgs['mgr_url'] or 'https:' in cfgs['mgr_url']):
                cfgs['mgr_url'] = 'http://' + cfgs['mgr_url']

            validate_url_v1 = '%s/api/v1/clusters' % cfgs['mgr_url']
            content = ParseHttp(cfgs['mgr_user'], cfgs['mgr_pwd']).get(validate_url_v1)
            if len(content) > 1:
                cluster_name = content['items'][int(cfgs['cluster_no'])-1]['name']
            else:
                cluster_name = content['items'][0]['name']

            hadoop_discover = HadoopDiscover(cfgs['mgr_user'], cfgs['mgr_pwd'], cfgs['mgr_url'], cluster_name)
            cfgs['node_list'] = ','.join(hadoop_discover.get_rsnodes())
    else:
        node_lists = expNumRe(raw_input('Enter list of Nodes separated by comma, support numeric RE, i.e. n[01-12]: '))

        # check if node list is expanded successfully
        if len([1 for node in node_lists if '[' in node]):
            err('Failed to expand node list, please check your input.')

        cfgs['node_list'] = ','.join(node_lists)

    if options.perf:
        mode = 'perf'
    else:
        mode = 'discover'

    if options.logfile:
        results = wrapper.run(cfgs, options, mode=mode, pwd=pwd, log_file=options.logfile)
    else:
        results = wrapper.run(cfgs, options, mode=mode, pwd=pwd)

    format_output('Discover results')

    if mode == 'discover':
        if options.json:
            output = json.dumps(results)
        else:
            hosts = 'Hosts: ' + ','.join([result['hostname']['value'] for result in results])
            output = hosts + '\n' + overview(results) + '\n'
            if options.all:
                output += detail_view(results) + '\n'
                output += dependency_view(results)
    elif mode == 'perf':
        if options.json:
            output = json.dumps(results)
        else:
            output = ''
            for result in results:
                if not result: continue
                output += '%s\n' % result

    with open('%s/logs/discover_result' % INSTALLER_LOC, 'w') as f:
        f.write(output)

    output = output.replace(STAT_OK, C_STAT_OK)
    output = output.replace(STAT_WARN, C_STAT_WARN)
    output = output.replace(STAT_ERR, C_STAT_ERR)
    print output

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print '\nAborted...'
