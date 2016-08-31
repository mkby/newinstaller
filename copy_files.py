#!/usr/bin/env python
# this script should be run on installer node

import os
import sys
import subprocess
import json
from threading import Thread
from common import Remote, run_cmd, DBCFG_FILE, err

def run(pwd):
    """ gen ssh key on local and copy to all nodes 
        copy traf package file from local to all nodes 
    """
    dbcfgs = json.loads(dbcfgs_json)
    hosts = dbcfgs['node_list'].split(',')
    traf_package = dbcfgs['traf_package']

    key_file = '/tmp/id_rsa'
    run_cmd('echo -e "y" | ssh-keygen -t rsa -N "" -f %s' % key_file)

    files = [key_file, key_file+'.pub', traf_package]

    remote_insts = [ Remote(h, pwd=pwd) for h in hosts ]
    threads = [Thread(target=r.copy, args=(files, '/tmp' )) for r in remote_insts]
    for t in threads: t.start()
    for t in threads: t.join()
    for r in remote_insts:
        if r.rc != 0: err('Failed to copy files to %s' % r.host)

    #run_cmd('rm -rf %s*' % key_file)

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')

try:
    pwd = sys.argv[2]
except IndexError:
    pwd = ''

run(pwd)
