#!/usr/bin/env python

import os
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
    print pt

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

    print pt

def main():
    cfgs = defaultdict(str)

    if os.path.exists(DBCFG_FILE):
        cfgs = ParseInI(DBCFG_FILE).load()
    else:
        node_lists = expNumRe(raw_input('Enter list of Nodes separated by comma, support numeric RE, i.e. n[01-12]: '))

        # check if node list is expanded successfully
        if len([1 for node in node_lists if '[' in node]):
            err('Failed to expand node list, please check your input.')

        cfgs['node_list'] = ','.join(node_lists)

    options = get_options()

    results = run(cfgs, options, mode='discover')


    #TODO: save discover results to log file with a pretty format
    #results = [{'eason-1': '{"ext_interface": "eth0", "python_ver": "2.6.6", "mem_free": "1.9 GB", "cpu_model": "Intel Xeon E312xx (Sandy Bridge)", "cpu_cores": 2, "mem_total": "7.7 GB", "default_java": "1.7", "linux": "centos-6.7-Final", "rootdisk_free": "9.3G", "hbase": "1.0.0-cdh5.4.8", "arch": "x86_64", "pidmax": "65535"}'}, {'eason-2': '{"ext_interface": "eth0", "python_ver": "2.6.6", "mem_free": "2.6 GB", "cpu_model": "Intel Xeon E312xx (Sandy Bridge)", "cpu_cores": 2, "mem_total": "7.7 GB", "default_java": "1.7", "linux": "centos-6.7-Final", "rootdisk_free": "8.3G", "hbase": "1.0.0-cdh5.4.8", "arch": "x86_64", "pidmax": "65535"}'}]

    format_output('Discover results')

    if len(results) > 4:
        output_row(results)
    else:
        output_column(results)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt,EOFError):
        print '\nAborted...'
