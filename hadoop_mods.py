#!/usr/bin/env python
import time
import base64
import sys
from common import *

cfgs = ParseJson('db_config').jload()
modcfgs = ParseJson('mod_cfgs.json').jload()

MOD_CFGS = modcfgs['MOD_CFGS']
HBASE_MASTER_CONFIG = modcfgs['HBASE_MASTER_CONFIG']
HBASE_RS_CONFIG = modcfgs['HBASE_RS_CONFIG']
HDFS_CONFIG = modcfgs['HDFS_CONFIG']
ZK_CONFIG = modcfgs['ZK_CONFIG']

CLUSTER_URL_PTR = '%s/api/v1/clusters/%s'
RESTART_URL_PTR = CLUSTER_URL_PTR + '/commands/restart'
RESTART_SRV_URL_PTR = CLUSTER_URL_PTR + '/services/%s/commands/restart'
SRVCFG_URL_PTR = CLUSTER_URL_PTR + '/services/%s/config'
RSGRP_BASEURL_PTR = '%s/api/v6/clusters/%s/services/%s/roleConfigGroups'
DEPLOY_CFG_URL_PTR = '%s/api/v6/clusters/%s/commands/deployClientConfig'
CMD_STAT_URL_PTR = '%s/api/v1/commands/%s'

class CDHMod:
    """ Modify CDH configs for trafodion and restart CDH services """
    def __init__(self, user, passwd, url, cluster_name):
        self.url = url
        self.cluster_name = cluster_name
        self.p = ParseHttp(user, passwd)

    def __retry_check(self, cid, maxcnt, interval):
        stat_url = CMD_STAT_URL_PTR % (self.url, cid)
        stat = self.p.get(stat_url)
        retry_cnt = 0
        while not (stat['success'] == True and stat['active'] == False):
            retry_cnt += 1
            flush_str = '.' * retry_cnt
            print '\rCheck CDH services restart status (timeout: %dmin) %s' % (maxcnt*interval/60, flush_str),
            sys.stdout.flush()
            time.sleep(interval)
            stat = self.p.get(stat_url)
            if retry_cnt == maxcnt: return False
        return True
            
    def mod(self):
        hdfs_service = cfgs['hdfs_service_name']
        hbase_service = cfgs['hbase_service_name']
        zk_service = cfgs['zookeeper_service_name']
        services = { hdfs_service:HDFS_CONFIG, hbase_service:HBASE_MASTER_CONFIG, zk_service:ZK_CONFIG }

        for srv, cfg in services.iteritems():
            srvcfg_url= SRVCFG_URL_PTR % (self.url, self.cluster_name, srv)
            self.p.put(srvcfg_url, cfg)

        # set configs in each regionserver group
        rsgrp_baseurl = RSGRP_BASEURL_PTR % (self.url, self.cluster_name, hbase_service)
        rscfg = self.p.get(rsgrp_baseurl)
        rsgrp_urls = [ '%s/%s/config' % (rsgrp_baseurl, r['name']) for r in rscfg['items'] if r['roleType'] == 'REGIONSERVER' ]

        for rsgrp_url in rsgrp_urls:
            self.p.put(rsgrp_url, HBASE_RS_CONFIG)

    def restart(self):
        restart_url = RESTART_URL_PTR % (self.url, self.cluster_name)
        deploy_cfg_url = DEPLOY_CFG_URL_PTR % (self.url, self.cluster_name)

        info('Restarting CDH services ...')
        rc1 = self.p.post(restart_url)
        if self.__retry_check(rc1['id'], 40, 15):
            ok('Restart CDH successfully!')
        else:
            err('Failed to restart CDH, max retry count reached')

        rc2 = self.p.post(deploy_cfg_url)
        if self.__retry_check(rc2['id'], 30, 10):
            ok('Deploy client config successfully!')
        else:
            err('Failed to deploy CDH client config, max retry count reached')


class HDPMod:
    """ Modify HDP configs for trafodion and restart HDP services """
    def __init__(self, user, passwd, url, cluster_name):
        self.url = url
        self.cluster_name = cluster_name
        self.p = ParseHttp(user, passwd)

    def mod(self):
        cluster_url = CLUSTER_URL_PTR % (self.url, self.cluster_name)
        desired_cfg_url = cluster_url + '?fields=Clusters/desired_configs'
        cfg_url = cluster_url + '/configurations?type={0}&tag={1}'
        desired_cfg = self.p.get(desired_cfg_url)

        for config_type in MOD_CFGS.keys():
            desired_tag = desired_cfg['Clusters']['desired_configs'][config_type]['tag']
            current_cfg = self.p.get(cfg_url.format(config_type, desired_tag))
            tag = 'version' + str(int(time.time() * 1000000))
            new_properties = current_cfg['items'][0]['properties']
            new_properties.update(MOD_CFGS[config_type])
            config = {
              'Clusters': {
                'desired_config': {
                  'type': config_type,
                  'tag': tag,
                  'properties': new_properties
                 }
              }
            }
            self.p.put(cluster_url, config)


    def restart(self):
        srv_baseurl = CLUSTER_URL_PTR % (self.url, self.cluster_name) + '/services/'
        srvs = ['HBASE', 'ZOOKEEPER', 'HDFS']

        # Stop
        info('Restarting HDP services ...')
        for srv in srvs:
            srv_url = srv_baseurl + srv
            config = {'RequestInfo': {'context' :'Stop %s services' % srv}, 'ServiceInfo': { 'state' : 'INSTALLED' }}
            rc = self.p.put(srv_url, config)

            # check stop status
            if rc:
                stat = self.p.get(srv_url)

                retry_cnt,  maxcnt, interval = 0, 30, 5
                while stat['ServiceInfo']['state'] != 'INSTALLED':
                    retry_cnt += 1
                    flush_str = '.' * retry_cnt
                    print '\rCheck HDP service %s stop status (timeout: %dmin) %s' % (srv, maxcnt*interval/60, flush_str),
                    sys.stdout.flush()
                    time.sleep(interval)
                    stat = self.p.get(srv_url)
                    if retry_cnt == maxcnt: err('Failed to stop HDP service %s, timeout' % srv)
                # wrap line
                print
            else:
                info('HDP service %s had already been stopped' % srv)

        time.sleep(3)
        # Start
        config = {'RequestInfo': {'context' :'Start All services'}, 'ServiceInfo': { 'state' : 'STARTED' }}
        rc = self.p.put(srv_baseurl, config)

        # check start status
        if rc:
            result_url = rc['href']
            stat = self.p.get(result_url)
            retry_cnt, maxcnt, interval = 0, 120, 5
            while stat['Requests']['request_status'] != 'COMPLETED':
                retry_cnt += 1
                flush_str = '.' * retry_cnt
                print '\rCheck HDP services start status (timeout: %dmin) %s' % (maxcnt*interval/60, flush_str),
                sys.stdout.flush()
                time.sleep(interval)
                stat = self.p.get(result_url)
                if retry_cnt == maxcnt: err('Failed to start all HDP services')
            ok('HDP services started successfully!')
        else:
            info('HDP services had already been started')
            
def apache_restart(hadoop_home, hbase_home):
    # stop
    run_cmd(hbase_home + '/bin/stop_hbase.sh')
    run_cmd(hadoop_home + '/sbin/stop_dfs.sh')
    # start
    run_cmd(hadoop_home + '/sbin/start_dfs.sh')
    run_cmd(hbase_home + '/bin/start_hbase.sh')


def main():
    if 'CDH' in cfgs['distro']:
        cdh = CDHMod(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']), cfgs['mgr_url'], cfgs['cluster_name'])
        cdh.mod()
        cdh.restart()
    elif 'HDP' in cfgs['distro']:
        hdp = HDPMod(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']), cfgs['mgr_url'], cfgs['cluster_name'])
        hdp.mod()
        hdp.restart()
    elif 'apache' in cfgs['distro']:
        # apache mod should be run on all nodes, so put it in another script
        apache_restart(cfgs['hadoop_home'], cfgs['hbase_home'])


if __name__ == '__main__':
    main()
