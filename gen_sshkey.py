#!/usr/bin/env python
# this script should be run on installer node

import os
import sys
import subprocess
from threading import Thread
from common import Remote, run_cmd, ParseJson, DBCFG_FILE, err

def run(pwd):
    """ gen ssh key on local and copy to all nodes' HOME """
    #dbcfgs = ParseJson(DBCFG_FILE).jload()
    #hosts = dbcfgs['node_list'].split()
    hosts = ['eason-1', 'eason-2']

    run_cmd('echo -e "y" | ssh-keygen -t rsa -N "" -f /tmp/id_rsa')
    files = ['/tmp/id_rsa', '/tmp/id_rsa.pub']
    remote_insts = [ Remote(h, pwd=pwd) for h in hosts ]

    threads = [Thread(target=r.copy, args=(files, )) for r in remote_insts]
    for t in threads: t.start()
    for t in threads: t.join()
    for r in remote_insts:
        if r.rc != 0: err('Failed to copy files to %s' % r.host)

    run_cmd('rm -rf /tmp/id_rsa*')

# main
try:
    pwd = sys.argv[1]
except IndexError:
    pwd = ''

run(pwd)
