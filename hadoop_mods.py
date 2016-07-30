#!/usr/bin/env python
import time
from common import ParseHttp, ParseXML

mod_cfgs = {
    'hbase-site': {
        'hbase.master.distributed.log.splitting': 'false',
        'hbase.coprocessor.region.classes': 'org.apache.hadoop.hbase.coprocessor.transactional.TrxRegionObserver,org.apache.hadoop.hbase.coprocessor.transactional.TrxRegionEndpoint,org.apache.hadoop.hbase.coprocessor.AggregateImplementation',
        'hbase.hregion.impl': 'org.apache.hadoop.hbase.regionserver.transactional.TransactionalRegion',
        'hbase.regionserver.region.split.policy': 'org.apache.hadoop.hbase.regionserver.ConstantSizeRegionSplitPolicy',
        'hbase.snapshot.enabled': 'true',
        'hbase.bulkload.staging.dir': '/hbase-staging',
        'hbase.regionserver.region.transactional.tlog': 'true',
        'hbase.snapshot.master.timeoutMillis': '600000',
        'hbase.snapshot.region.timeout': '600000',
        'hbase.client.scanner.timeout.period': '600000'
    },
    'hdfs-site': { 'dfs.namenode.acls.enabled': 'true' },
    'zoo.cfg': { 'maxClientCnxns': '0' }
}

def cloudera_mod():
    pass

def ambari_mod(user, passwd, url, cluster_name):
    cluster_url = url + 'api/v1/clusters' + cluster_name
    desired_cfg_url = cluster_url + '?fields=Clusters/desired_configs'
    cfg_url = cluster_url + '/configurations?type={0}&tag={1}'
    p = ParseHttp(user, passwd)
    desired_cfg = p.get_config(desired_cfg_url)

    for config_type in mod_cfgs.keys():
        desired_tag = desired_cfg['Clusters']['desired_configs'][config_type]['tag']
        current_cfg = p.get_config(cfg_url.format(config_type, desired_tag))
        tag = 'version' + str(int(time.time() * 1000000))
        new_properties = current_cfg['items'][0]['properties']
        config = {
          'Clusters': {
            'desired_config': {
              'type': config_type,
              'tag': tag,
              'properties': properties
            }
          }
        }
        # modify configs
        new_properties.update(mod_cfgs[config_type])
        set_config(config)


def apache_mod(hdfs_xml, hbase_xml):
    hbasexml = ParseXML(hbase_xml)
    for n,v in mod_cfgs['hbase'].items():
        hbasexml.add_property(n, v)
    hbasexml.write_xml()

    hdfsxml = ParseXML(hdfs_xml)
    for n,v in mod_cfgs['hdfs'].items():
        hdfsxml.add_property(n, v)
    hdfsxml.write_xml()

