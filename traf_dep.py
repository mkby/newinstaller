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
import sys
import json
import platform
from common import run_cmd, err

def run():
    """ install Trafodion dependencies """
    dbcfgs = json.loads(dbcfgs_json)
    # backlog, not used
    epelrepo='''
[epel]
name=Extra Packages for Enterprise Linux $releasever - $basearch
mirrorlist=https://mirrors.fedoraproject.org/metalink?repo=epel-$releasever&arch=$basearch
enabled=1
gpgcheck=0
'''
    if dbcfgs['offline_mode'] == 'Y':
        # local repo was set if enable offline mode
        print 'Installing pdsh in offline mode ...'
        run_cmd('yum install -y pdsh pdsh-rcmd-ssh')
    else:
        pdsh_installed = run_cmd('rpm -qa|grep -c pdsh')
        if pdsh_installed == '0':
            release = platform.release()
            releasever, arch = re.search('el(\d).(\w+)',release).groups()

            if releasever == '7':
                pdsh_pkg = 'http://mirrors.neusoft.edu.cn/epel/7/%s/p/pdsh-2.31-1.el7.%s.rpm' % (arch, arch)
                pdsh_ssh_pkg = 'http://mirrors.neusoft.edu.cn/epel/7/%s/p/pdsh-rcmd-ssh-2.31-1.el7.%s.rpm' % (arch, arch)
            elif releasever == '6':
                pdsh_pkg = 'http://mirrors.neusoft.edu.cn/epel/6/%s/pdsh-2.26-4.el6.%s.rpm' % (arch, arch)
                pdsh_ssh_pkg = 'http://mirrors.neusoft.edu.cn/epel/6/%s/pdsh-rcmd-ssh-2.26-4.el6.%s.rpm' % (arch, arch)
            else:
                err('Unsupported Linux version')

            print 'Installing pdsh ...'
            run_cmd('yum install -y %s' % pdsh_pkg)
            run_cmd('yum install -y %s' % pdsh_ssh_pkg)
        

    package_list= [
        'apr',
        'apr-util',
        'expect',
        'gzip',
        'libiodbc-devel',
        'lzo',
        'lzop',
        'openldap-clients',
        'perl-DBD-SQLite',
        'perl-Params-Validate',
        'perl-Time-HiRes',
        'sqlite',
        'snappy',
        'unixODBC-devel',
        'unzip'
    ]

    all_pkg_list = run_cmd('rpm -qa')
    for pkg in package_list:
        if pkg in all_pkg_list: 
            print 'Package %s had already been installed' % pkg
        else:
            print 'Installing %s ...' % pkg
            run_cmd('yum install -y %s' % pkg)

# main
try:
    dbcfgs_json = sys.argv[1]
except IndexError:
    err('No db config found')
run()