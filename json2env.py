#!/usr/bin/env python

import os
import sys

from common import ParseJson

try:
    json_file = sys.argv[1]
except IndexError:
    exit(1)

if not os.path.exists(json_file): exit(1)

cfgs = ParseJson(json_file).jload()

output_file = json_file + '.source'

with open(output_file, 'w') as f:
    for k,v in cfgs.iteritems():
        f.write('export %s="%s"\n' % (k.upper(), v))

