#!/usr/bin/env python
from common import ParseJson, ParseXML, ok

modcfgs = ParseJson('mod_cfgs.json').jload()
MOD_CFGS = modcfgs['MOD_CFGS']

def apache_mod(hdfs_xml, hbase_xml):
    hbasexml = ParseXML(hbase_xml)
    for n,v in MOD_CFGS['hbase'].items():
        hbasexml.add_property(n, v)
    hbasexml.write_xml()

    hdfsxml = ParseXML(hdfs_xml)
    for n,v in MOD_CFGS['hdfs'].items():
        hdfsxml.add_property(n, v)
    hdfsxml.write_xml()


def main():
    cfgs = ParseJson('db_config').jload()
    if 'APACHE' in cfgs['distro']:
        apache_mod(cfgs['hdfs_xml_file'], cfgs['hbase_xml_file'])
        print 'Apache Hadoop modification completed'

if __name__ == '__main__':
    main()
