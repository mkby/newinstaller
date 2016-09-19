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

### this script should be run on all nodes with sudo user ###

from common import ParseJson, ParseXML, err

dbcfgs = json.loads(dbcfgs_json)

def run():
    if 'APACHE' in dbcfgs['distro']:
        modcfgs = ParseJson(MODCFG_FILE).load()
        MOD_CFGS = modcfgs['MOD_CFGS']

        hdfs_xml_file = dbcfgs['hdfs_xml_file']
        hbase_xml_file = dbcfgs['hbase_xml_file']

        hbasexml = ParseXML(hbase_xml)
        for n,v in MOD_CFGS['hbase'].items():
            hbasexml.add_property(n, v)
        hbasexml.write_xml()

        hdfsxml = ParseXML(hdfs_xml)
        for n,v in MOD_CFGS['hdfs'].items():
            hdfsxml.add_property(n, v)
        hdfsxml.write_xml()

        print 'Apache Hadoop modification completed'
    else:
        print 'no apache distribution found, skipping'

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()
