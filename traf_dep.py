#!/usr/bin/env python
# this script should be run on all nodes with sudo user

import re
import sys
import json
import platform
from common import run_cmd

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
