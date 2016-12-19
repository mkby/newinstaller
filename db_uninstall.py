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

import sys
import os
import getpass
from optparse import OptionParser
from scripts.common import run_cmd,format_output,err,expNumRe,ParseInI

def get_options():
    usage = 'usage: %prog [options]\n'
    usage += '  Trafodion uninstall script. It will uninstall trafodion rpm\n\
  and remove trafodion user and home folder.'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config-file", dest="cfgfile", metavar="FILE",
                      help="Json format file. If provided, all install prompts \
                            will be taken from this file and not prompted for.")
    parser.add_option("--enable-pwd", action="store_true", dest="pwd", default=False,
                      help="Prompt SSH login password for remote hosts. \
                            If set, \'sshpass\' tool is required.")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="Verbose mode, will print commands.")

    (options, args) = parser.parse_args()
    return options

def main():
    """ db_uninstaller main loop """

    # handle parser option
    options = get_options()

    notify = lambda n: raw_input('Uninstall Trafodion on [%s] [N]: ' % n)

    node_list = ''

    format_output('EsgynDB Uninstall Start')
    
    if options.pwd:
        pwd = getpass.getpass('Input remote host SSH Password: ')
    else:
        pwd = ''

    if options.cfgfile:
        if not os.path.exists(options.cfgfile):
            err('Cannot find config file \'%s\'' % options.cfgfile)
        config_file = options.cfgfile
        p = ParseInI(config_file, 'dbconfigs')
        cfgs = p.load()
        node_list = cfgs['node_list']
    else:
        node_lists = raw_input('Enter Trafodion node list to uninstall(separated by comma): ')
        if not node_lists: err('Empty value\n')
        node_list = ','.join(expNumRe(node_lists))

    rc = notify(node_list)
    if rc.lower() != 'y': sys.exit(1)
    nodes = node_list.split(',')
    first_node = nodes[0]

    ssh_cmd = 'ssh'
    if pwd != '':
        ssh_cmd = 'sshpass -p %s' % pwd

    # stop trafodion on the first node
    run_cmd('%s %s sudo su trafodion -l -c \"ckillall\" ' % (ssh_cmd, first_node))
    # remove trafodion userid and group on all trafodion nodes, together with folders
    for node in nodes:
        run_cmd('%s %s sudo /usr/sbin/userdel -rf trafodion' % (ssh_cmd, node))
        run_cmd('%s %s sudo /usr/sbin/groupdel trafodion' % (ssh_cmd, node))
        run_cmd('%s %s sudo rm -rf /etc/trafodion*' % (ssh_cmd, node))
    
    format_output('EsgynDB Uninstall Complete')

if __name__ == "__main__":
    main()
