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
from scripts.constants import DBCFG_FILE
from scripts.common import err_m, err, ParseInI, ParseHttp, expNumRe, format_output, HadoopDiscover
from scripts import wrapper


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
    parser.add_option("-p", "--net-perf", action="store_true", dest="perf", default=False,
                      help="Run network bandwidth tests.")
    parser.add_option("--enable-pwd", action="store_true", dest="pwd", default=False,
                      help="Prompt SSH login password for remote hosts. \
                            If set, \'sshpass\' tool is required.")
    (options, args) = parser.parse_args()
    return options

# row format
def output_row(results):
    items = []
    for result in results:
        host = result['hostname']

        title = ['Host']
        item = [host]
        cfg_tuples = sorted(result.items())
        for key, value in cfg_tuples:
            title.append(key)
            item.append(value)
        items.append(item)

    pt = PrettyTable(title)
    for item in items: pt.add_row(item)

    return str(pt)

# column format
def output_column(results):
    items = []
    for result in results:
        host = result['hostname']

        item = []
        title = []
        cfg_tuples = sorted(result.items())
        for key, value in cfg_tuples:
            title.append(key)
            item.append(value)
        items.append([host, item])

    pt = PrettyTable()
    pt.add_column('Host', title)
    for item in items:
        pt.add_column(item[0], item[1])

    return str(pt)

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
        ### perform actual installation ###
        results = wrapper.run(cfgs, options, mode=mode, pwd=pwd, log_file=options.logfile)
    else:
        results = wrapper.run(cfgs, options, mode=mode, pwd=pwd)

    format_output('Discover results')

    if mode == 'discover':
        if options.json:
            output = results
        else:
            if len(results) > 4:
                output = output_row(results)
            else:
                output = output_column(results)
    elif mode == 'perf':
        output = ''
        for result in results:
            host, content = result.items()[0]
            if not content: continue
            output += content + '\n'

    print output

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print '\nAborted...'
