#!/usr/bin/env python

# This script should be run on all nodes with trafodion user

import sys
import json
from common import run_cmd, err

def run():
    dbcfgs = json.loads(dbcfgs_json)

    TRAF_DIR = '%s-%s' % (dbcfgs['traf_basename'], dbcfgs['traf_version'])

    # untar traf package
    TRAF_PACKAGE_FILE = '/tmp/' + dbcfgs['traf_package'].split('/')[-1]
    run_cmd('mkdir -p %s' % TRAF_DIR)
    run_cmd('tar xf %s -C %s' % (TRAF_PACKAGE_FILE, TRAF_DIR))

    print 'Trafodion package uncompressed successfully!'

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
