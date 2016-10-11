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
from prettytable import PrettyTable
from optparse import OptionParser
from collections import defaultdict
from common import *
from py_wrapper import run

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
    parser.add_option("--no-passwd", action="store_true", dest="pwd", default=True,
                help="Not Prompt SSH login password for remote hosts.")

    (options, args) = parser.parse_args()
    return options

# row format
def output_row(results):
    items = []
    for result in results:
        host, content = result.items()[0]
        cfg_dict = json.loads(content)

        cfg_tuples = sorted(cfg_dict.items())
        title = ['Host']
        item = [host]
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
        host, content = result.items()[0]
        cfg_dict = json.loads(content)

        item = []
        title = []
        cfg_tuples = sorted(cfg_dict.items())
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
            log_err('Cannot find config file \'%s\'' % options.cfgfile)
        config_file = options.cfgfile
    else:
        config_file = DBCFG_FILE

    if os.path.exists(config_file):
        cfgs = ParseInI(config_file).load()
    else:
        node_lists = expNumRe(raw_input('Enter list of Nodes separated by comma, support numeric RE, i.e. n[01-12]: '))

        # check if node list is expanded successfully
        if len([1 for node in node_lists if '[' in node]):
            err('Failed to expand node list, please check your input.')

        cfgs['node_list'] = ','.join(node_lists)


    results = run(cfgs, options, mode='discover')


    print results

    format_output('Discover results')

    if len(results) > 4:
        output = output_row(results)
    else:
        output = output_column(results)

    print output
    with open('discover_result', 'w') as f:
        f.write('Discover Date: %s\n' % time.strftime('%Y-%m-%d %H:%M'))
        f.write(output)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt,EOFError):
        print '\nAborted...'
