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

import re
import os
import json
import sys
import platform
from glob import glob
from constants import DEF_CORE_SITE_XML, DEF_HBASE_HOME, DEF_HADOOP_HOME, \
                      SSH_CONFIG_FILE, NA, OK, WARN, ERR, UNKNOWN
from common import run_cmd2, cmd_output, err, get_sudo_prefix, CentralConfig, ParseXML

PREFIX = 'get_'
CCFG = CentralConfig()

def deco(func):
    def wrapper(self):
        if PREFIX in func.__name__:
            name = func.__name__.replace(PREFIX, '')
            value = func(self)
            return name, {'value': value, 'doc': func.__doc__}
        else:
            return
    return wrapper

def deco_warn_err(func):
    """ append warning or error status based on the threshold settings in configs """
    def wrapper(self):
        if PREFIX in func.__name__:
            name = func.__name__.replace(PREFIX, '')
            value = func(self)

            items = CCFG.get(name)
            cmpr_operator = items['cmpr']
            warn = error = 0
            if items.has_key(WARN):
                warn = int(items[WARN])

            if items.has_key(ERR):
                error = int(items[ERR])

            if cmpr_operator == 'lt':
                if int(value) < warn:
                    if int(value) < error:
                        status = ERR
                    else:
                        status = WARN
                else:
                    status = OK
            elif cmpr_operator == 'gt':
                if int(value) > warn:
                    status = WARN
                else:
                    status = OK

            value = str(value)
            warn = str(warn)
            if items.has_key('unit'):
                value += items['unit']
                warn += items['unit']

            dic = {'value': value, 'status': status, 'doc': func.__doc__}
            if status != OK:
                dic['expected'] = warn
            return name, dic
        else:
            return
    return wrapper

def deco_valid_value(func):
    """ append status if values found in configs """
    def wrapper(self):
        if PREFIX in func.__name__:
            name = func.__name__.replace(PREFIX, '')
            value = func(self)
            avl_values = CCFG.get(name) # list
            if value in avl_values:
                status = OK
            else:
                status = ERR
            return name, {'value': value, 'status': status, 'doc': func.__doc__}
        else:
            return
    return wrapper

def deco_val_chk(func):
    """ append status based on func return value/status """
    def wrapper(self):
        if PREFIX in func.__name__:
            name = func.__name__.replace(PREFIX, '')
            value, status = func(self)
            return name, {'value': value, 'status': status, 'doc': func.__doc__}
        else:
            return
    return wrapper

class Discover(object):
    """ discover functions, to add a new discover function,
        simply add a new def with name get_xx and decorated
        by 'deco', then return result in string or dict format:

        @deco
        def get_xx(self):
            # do something
            return result
    """

    def __init__(self, dbcfgs):
        self.CPUINFO = cmd_output('cat /proc/cpuinfo')
        self.MEMINFO = cmd_output('cat /proc/meminfo')
        self.SYSCTLINFO = cmd_output('sysctl -a')
        self.PKGINFO = cmd_output('rpm -qa').split('\n')
        self.DFINFO = cmd_output('df').split('\n')
        self.dbcfgs = dbcfgs

    def _parse_string(self, info, string):
        try:
            info = info.split('\n')
            string_line = [line for line in info if string in line][0]
        except IndexError:
            err('Cannot get %s info' % string)

        return string_line

    def _get_cpu_info(self, string):
        return self._parse_string(self.CPUINFO, string).split(':')[1].strip()

    def _get_mem_info(self, string):
        return self._parse_string(self.MEMINFO, string).split(':')[1].split()[0]

    def _get_sysctl_info(self, string):
        return self._parse_string(self.SYSCTLINFO, string).split('=')[1].strip()

    @deco_val_chk
    def get_arch(self):
        """CPU architecture"""
        arch = platform.processor()
        if not arch:
            return UNKNOWN, ERR
        else:
            return arch, OK

    @deco_val_chk
    def get_sudo(self):
        """Sudo access"""
        rc = run_cmd2('%s echo -n "check sudo access" > /dev/null 2>&1' % get_sudo_prefix())
        if rc:
            return 'not set', ERR
        else:
            return 'set', OK

    @deco_val_chk
    def get_ssh_pam(self):
        """SSH PAM settings"""
        if cmd_output('grep "^UsePAM yes" %s' % SSH_CONFIG_FILE):
            return 'set', OK
        else:
            return 'not set', ERR

    @deco_val_chk
    def get_loopback(self):
        """Localhost setting in /etc/hosts"""
        etc_hosts = cmd_output('cat /etc/hosts')
        loopback = r'127.0.0.1\s+localhost\s+localhost.localdomain\s+localhost4\s+localhost4.localdomain4'
        if re.findall(loopback, etc_hosts):
            return 'set', OK
        else:
            return 'not set', ERR

    @deco_val_chk
    def get_network_mgr_status(self):
        """NetworkManager service status"""
        if not run_cmd2('service NetworkManager status'):
            return 'running', WARN
        else:
            return 'not running', OK

    @deco_val_chk
    def get_ntp_status(self):
        """Ntp service status"""
        if not run_cmd2('service ntpd status'):
            return 'running', OK
        elif not run_cmd2('service chronyd status'):
            return 'running', OK
        else:
            return 'not running', ERR

    @deco_val_chk
    def get_hive(self):
        """Hive status"""
        hive_stat = cmd_output('which hive')
        if 'no hive' in hive_stat:
            return 'not found', ERR
        else:
            return 'installed', OK

    @deco_val_chk
    def get_home_nfs(self):
        """NFS on /home"""
        nfs_home = cmd_output('mount|grep -c "on /home type nfs"')
        if int(nfs_home):
            return 'mounted', ERR
        else:
            return 'not mounted', OK

    @deco_val_chk
    def get_firewall_status(self):
        """Firewall status"""
        iptables_stat = cmd_output('iptables -nL|grep -vE "(Chain|target)"')
        if iptables_stat:
            return 'Running', WARN
        else:
            return 'Stopped', OK

    @deco_val_chk
    def get_traf_status(self):
        """Trafodion running status"""
        mon_process = cmd_output('ps -ef|grep -v grep|grep -c "monitor COLD"')
        if int(mon_process) > 0:
            return 'Running', WARN
        else:
            return 'Stopped', OK

    @deco_val_chk
    def get_fqdn(self):
        """FQDN"""
        fqdn = cmd_output('hostname -f')
        if not '.' in fqdn:
            return fqdn, WARN
        else:
            return fqdn, OK

    @deco_valid_value
    def get_hbase_ver(self):
        """HBase version"""
        if self.dbcfgs.has_key('hbase_home'): # apache distro
            hbase_home = self.dbcfgs['hbase_home']
        else:
            hbase_home = DEF_HBASE_HOME
        hbase_ver = cmd_output('%s/bin/hbase version | head -n1' % hbase_home)

        try:
            hbase_ver = re.search(r'HBase (\d\.\d)', hbase_ver).groups()[0]
        except AttributeError:
            return NA
        return hbase_ver

    @deco_valid_value
    def get_linux_ver(self):
        """Linux version"""
        os_dist, os_ver = platform.dist()[:2]
        return '%s%s' % (os_dist, os_ver.split('.')[0])

    def _get_disk_free(self, path):
        disk_free = [l.split()[-3] for l in self.DFINFO if l.split()[-1] == path]
        if disk_free:
            return float(disk_free[0])
        else:
            return 0

    def _get_disks(self):
        SYS_BLOCK = '/sys/block'
        devices = cmd_output('ls %s' % SYS_BLOCK).split('\n')
        disk_devices = [device for device in devices if os.path.exists('%s/%s/device' % (SYS_BLOCK, device))]
        return disk_devices

    @deco_warn_err
    def get_user_disk_free(self):
        """Free data disk spaces"""
        disk_devices = self._get_disks()
        disk_fs = []
        all_fs = [l.split()[0] for l in self.DFINFO]
        for fs in all_fs:
            for device in disk_devices:
                if device in fs:
                    disk_fs.append(fs)

        disk_df = [df for df in self.DFINFO if df.split()[0] in disk_fs and df.split()[-1] != '/home' and df.split()[-1] != '/' and df.split()[-1] != '/opt' and df.split()[-1] != '/boot']
        user_disk_free = sum([self._get_disk_free(l.split()[-1]) for l in disk_df])

        return "%0.0f" % round(float(user_disk_free) / (1024 * 1024), 2)

    @deco_warn_err
    def get_install_disk_free(self):
        """Free system disk spaces"""
        install_disk_free = self._get_disk_free('/') + self._get_disk_free('/home') + self._get_disk_free('/opt')
        return "%0.0f" % round(float(install_disk_free) / (1024 * 1024), 2)

    @deco_warn_err
    def get_disk_nums(self):
        """Disk numbers"""
        return len(self._get_disks())

    @deco_warn_err
    def get_net_bw(self):
        """Network Card bandwidth"""
        # output are several lines with 1 or 10 or other numbers
        net_bw = cmd_output('lspci -vv |grep -i ethernet |grep -o "[0-9]\+\s*Gb"|sed s"/\s\+Gb//g"').split('\n')
        net_bw.append(0) # add a default int when not detected
        bandwidth = max([int(bw) for bw in net_bw if type(bw) == int])

        return bandwidth

    @deco_warn_err
    def get_mem_total(self):
        """Total memory size"""
        mem = self._get_mem_info('MemTotal')
        mem_size = mem.split()[0]

        return "%0.0f" % round(float(mem_size) / (1024 * 1024), 2)

    @deco_warn_err
    def get_swap_pct(self):
        """Swap/Mem percentage"""
        swap = self._get_mem_info('SwapTotal')
        mem = self._get_mem_info('MemTotal')
        swap_size = swap.split()[0]
        mem_size = mem.split()[0]

        return str(int(swap_size)*100/int(mem_size))

    @deco_warn_err
    def get_tcp_time(self):
        """Kernel tcp keep alive time"""
        #net.ipv4.tcp_keepalive_time net.ipv4.tcp_keepalive_intvl net.ipv4.tcp_keepalive_probes
        return self._get_sysctl_info('net.ipv4.tcp_keepalive_time')

    @deco_warn_err
    def get_tcp_intvl(self):
        """Kernel tcp keep alive interval"""
        return self._get_sysctl_info('net.ipv4.tcp_keepalive_intvl')

    @deco_warn_err
    def get_tcp_probes(self):
        """Kernel tcp keep alive probes"""
        return self._get_sysctl_info('net.ipv4.tcp_keepalive_probes')

    @deco_warn_err
    def get_pid_max(self):
        """Kernel pid max"""
        return self._get_sysctl_info('kernel.pid_max')

    @deco
    def get_dependencies(self):
        """EsgynDB RPM dependencies"""
        dic = {}
        for pkg in self.PKGINFO:
            try:
                pkg_name =re.search(r'(.*?)-\d+\.\d+\.*', pkg).groups()[0]
            except AttributeError:
                pkg_name = pkg
            for reqpkg in CCFG.get('packages'):
                if reqpkg == pkg_name:
                    dic[reqpkg] = pkg.replace('%s-' % reqpkg, '')

        napkgs = list(set(CCFG.get('packages')).difference(set(dic.keys())))

        for pkg in napkgs:
            dic[pkg] = NA
        #return dic
        return 'ok'

    @deco
    def get_hadoop_distro(self):
        """Hadoop distro"""
        for pkg in self.PKGINFO:
            if 'cloudera-manager-agent' in pkg:
                #ls '%s/CDH-* -d' % PARCEL_DIR
                return 'CM' + re.search(r'cloudera-manager-agent-(\d\.\d\.\d).*', pkg).groups()[0]
            elif 'hdp-select' in pkg:
                return 'HDP' + re.search(r'hdp-select-(\d\.\d\.\d).*', pkg).groups()[0]
        return UNKNOWN

    @deco
    def get_default_java(self):
        """Default java version"""
        jdk_path = glob('/usr/java/*') + \
                   glob('/usr/jdk64/*') + \
                   glob('/usr/lib/jvm/java-*-openjdk.x86_64')

        jdk_list = {} # {jdk_version: jdk_path}
        for path in jdk_path:
            jdk_ver = cmd_output('%s/bin/javac -version' % path)

            try:
                main_ver, sub_ver = re.search(r'(\d\.\d\.\d)_(\d+)', jdk_ver).groups()
                # don't support JDK version less than 1.7.0_65
                if main_ver == '1.7.0' and int(sub_ver) < 65:
                    continue
                jdk_list[main_ver] = path
            except AttributeError:
                continue

        # auto detect JDK1.8
        if jdk_list.has_key('1.8.0'):
            return jdk_list['1.8.0']
        else:
            return NA

    def _get_core_site_info(self, name):
        if self.dbcfgs.has_key('hadoop_home'): # apache distro
            core_site_xml = '%s/etc/hadoop/core-site.xml' % self.dbcfgs['hadoop_home']
        else:
            core_site_xml = DEF_CORE_SITE_XML

        if os.path.exists(core_site_xml):
            p = ParseXML(core_site_xml)
            return p.get_property(name)
        else:
            return NA

    @deco
    def get_hadoop_auth(self):
        """Hadoop authentication"""
        return self._get_core_site_info('hadoop.security.authentication')

    @deco
    def get_hadoop_group_mapping(self):
        """Hadoop security group mapping"""
        mapping = self._get_core_site_info('hadoop.security.group.mapping')
        if 'ShellBasedUnixGroupsMapping' in mapping:
            return 'SHELL'
        elif 'LdapGroupsMapping' in mapping:
            return 'LDAP'
        else:
            return 'NONE'

    @deco
    def get_hdfs_ver(self):
        """HDFS version"""
        if self.dbcfgs.has_key('hadoop_home'): # apache distro
            hadoop_home = self.dbcfgs['hadoop_home']
        else:
            hadoop_home = DEF_HADOOP_HOME
        hdfs_ver = cmd_output('%s/bin/hdfs version | head -n1' % hadoop_home)
        if 'No such file or directory' in hdfs_ver:
            return NA
        return hdfs_ver

#    @deco
#    def get_cpu_model(self):
#        """CPU model"""
#        return self._get_cpu_info('model name')

    @deco
    def get_cpu_cores(self):
        """CPU cores"""
        return self.CPUINFO.count('processor')

    @deco
    def get_mem_free(self):
        """Current free memory size"""
        free = self._get_mem_info('MemFree')
        buffers = self._get_mem_info('Buffers')
        cached = self._get_mem_info('Cached')
        memfree = float(free) + float(buffers) + float(cached)

        return "%0.1f GB" % round(memfree / (1024 * 1024), 2)

    @deco
    def get_hostname(self):
        """Short hostname"""
        return cmd_output('hostname -s')

    @deco
    def get_ext_interface(self):
        """External network interface"""
        return cmd_output('ip route |grep default|awk \'{print $5}\'')

    @deco
    def get_python_ver(self):
        """Python version"""
        return platform.python_version()

    @deco
    def get_home_dir(self):
        """Trafodion home directory"""
        if self.dbcfgs.has_key('traf_user'):
            traf_user = self.dbcfgs['traf_user']
            return cmd_output("getent passwd %s | awk -F: '{print $6}' | sed 's/\/%s//g'" % (traf_user, traf_user))
        else:
            return ''

    @deco
    def get_core_pattern(self):
        """System Core pattern setting"""
        return cmd_output('cat /proc/sys/kernel/core_pattern')

def run():
    try:
        dbcfgs_json = sys.argv[1]
    except IndexError:
        err('No db config found')
    dbcfgs = json.loads(dbcfgs_json)
    discover = Discover(dbcfgs)
    methods = [m for m in dir(discover) if m.startswith(PREFIX)]
    result = {}
    for method in methods:
        key, value = getattr(discover, method)() # call method
        result[key] = value

    print json.dumps(result)

# main
if __name__ == '__main__':
    run()
