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
import json
import sys
import os
import platform
from common import cmd_output, err

PREFIX = 'get_'

def deco(func):
    def wrapper(self):
        if PREFIX in func.__name__:
            name = func.__name__.replace(PREFIX, '')
            return name, func(self)
        else:
            return 
    return wrapper


class Discover(object):
    """ discover functions, to add a new discover function,
        simply add a new def with name get_xx and decorated 
        by 'deco', then return result in string format:

        @deco
        def get_xx(self):
            # do something
            return result
    """

    def __init__(self):
        self.CPUINFO = cmd_output('cat /proc/cpuinfo')
        self.MEMINFO = cmd_output('cat /proc/meminfo')
        self.SYSCTLINFO = cmd_output('sysctl -a')

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

    @deco
    def get_linux(self):
        """ get linux version """
        return '-'.join(platform.dist()[:2])

    @deco
    def get_firewall_stat(self):
        """ get firewall running status """
        iptables_stat = cmd_output('iptables -nL|grep -vE "(Chain|target)"').strip()
        if iptables_stat:
            return 'Running'
        else:
            return 'Stopped'

    @deco
    def get_pidmax(self):
        """ get kernel pid max setting """
        return self._get_sysctl_info('kernel.pid_max')

    @deco
    def get_default_java(self):
        """ get java version """
        jdk_ver = cmd_output('javac -version')
        try:
            return re.search('(\d\.\d)', jdk_ver).groups()[0]
        except AttributeError:
            return 'no_def_Java'

    @deco
    def get_hive(self):
        """ get Hive status """
        hive_stat = cmd_output('which hive')
        if 'no hive' in hive_stat:
            return 'N/A'
        else:
            return 'OK'

    @deco
    def get_hbase(self):
        """ get HBase version """
        hbase_ver = cmd_output('hbase version | head -n1')
        try:
            return re.search('HBase (.*)', hbase_ver).groups()[0]
        except AttributeError:
            return 'N/A'
    
    @deco
    def get_cpu_model(self):
        """ get CPU model """
        return self._get_cpu_info('model name')

    @deco
    def get_cpu_cores(self):
        """ get CPU cores """
        return self.CPUINFO.count('processor')

    @deco
    def get_arch(self):
        """ get CPU architecture """
        arch = platform.processor()
        if not arch:
            arch = 'unknown_arch'
        return arch

    @deco
    def get_mem_total(self):
        """ get total memory size """
        mem = self._get_mem_info('MemTotal')
        memsize = mem.split()[0]

        return "%0.1f GB" % round(float(memsize) / (1024 * 1024), 2) 

    @deco
    def get_mem_free(self):
        """ get current free memory size """
        free = self._get_mem_info('MemFree')
        buffers = self._get_mem_info('Buffers')
        cached = self._get_mem_info('Cached')
        memfree = float(free) + float(buffers) + float(cached)

        return "%0.1f GB" % round(memfree / (1024 * 1024), 2) 

    @deco
    def get_ext_interface(self):
        """ get external network interface """
        return cmd_output('netstat -rn | grep "^0.0.0.0" | awk \'{print $8}\'').strip()

    @deco
    def get_rootdisk_free(self):
        """ get root disk space left """
        space = cmd_output('df -h|grep "\/$" | awk \'{print $4}\'')
        return space.strip()

    @deco
    def get_python_ver(self):
        """ get python version """
        return platform.python_version()

    @deco
    def get_traf_status(self):
        """ get trafodion running status """
        mon_process = cmd_output('ps -ef|grep -v grep|grep -c "monitor COLD"')
        if int(mon_process) > 1:
            return 'Running'
        else:
            return 'Stopped'

def run():
    discover = Discover()
    methods = [m for m in dir(discover) if m.startswith(PREFIX)]
    result = {}
    for method in methods:
        key, value = getattr(discover, method)() # call method
        result[key] = value

    print json.dumps(result)


# main
if __name__ == '__main__':
    run()
