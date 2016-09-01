#!/usr/bin/env python
# this script should be run on first trafodion node
# this script should be run as trafodion user

import os
import json
from common import *

def run():
    dbcfgs = json.loads(dbcfgs_json)

    nodes = dbcfgs['node_list'].split(',')
    scratch_locs = dbcfgs['scratch_locs'].split(',')

    # this script is running by trafodion user, so get sqroot from env
    sq_root = os.environ['MY_SQROOT']
    sqconfig_file = sq_root + '/sql/scripts/sqconfig'

    core, processor = run_cmd("lscpu|grep -E '(^CPU\(s\)|^Socket\(s\))'|awk '{print $2}'").split('\n')[:2]
    core = str(int(core)-1)

    lines = ['begin node\n']
    for node_id, node in enumerate(nodes):
        line = 'node-id=%s;node-name=%s;cores=0-%s;processors=%s;roles=connection,aggregation,storage\n' % (node_id, node, core, processor)
        lines.append(line)

    lines.append('end node\n')
    lines.append('\n')
    lines.append('begin overflow\n')

    for scratch_loc in scratch_locs:
        line = 'hdd %s\n' % scratch_loc
        lines.append(line)

    lines.append('begin overflow\n')

    with open(sqconfig_file, 'w') as f:
        f.writelines(lines)     

    print 'sqconfig generated successfully!'

#    run_cmd('sqgen')

    print 'sqgen ran successfully!'

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
