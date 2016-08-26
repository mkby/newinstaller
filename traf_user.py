#!/usr/bin/env python
# this script should be run on all nodes

import base64
from common import *

def run():
    """ create trafodion user, bashrc, setup passwordless SSH """
    dbcfgs = ParseJson(DBCFG_FILE).jload()
    #traf_user = dbcfgs['traf_user']
    #traf_pwd = base64.b64decode(dbcfgs['traf_pwd'])
    traf_user = 'trafodion'
    traf_pwd = 'traf'
    traf_group = traf_user

    traf_home = cmd_output('cat /etc/default/useradd |grep HOME |cut -d "=" -f 2')[0].strip()
    traf_user_dir = '%s/%s' % (traf_home, traf_user)

    # create trafodion user and group
    if not cmd_output('getent passwd %s' % traf_user)[0]:
        run_cmd('useradd --shell /bin/bash -m %s -g %s --password "$(openssl passwd %s)"' % (traf_user, traf_group, traf_pwd))

    if not cmd_output('getent group %s' % traf_user)[0]:
        run_cmd('groupadd %s > /dev/null 2>&1' % traf_user)
    
    # set ssh key
    run_cmd_as_user(traf_user, 'echo -e "y" | ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa')
    # the key is generated in another script running on the installer node
    key_file = '/tmp/id_rsa'
    run_cmd('cp %s{,.pub} %s/.ssh/' % (key_file, traf_user_dir))
    run_cmd('chown -R %s:%s %s/.ssh/' % (traf_user, traf_group, traf_user_dir))

    auth_key_file = '%s/.ssh/authorized_keys' % traf_user
    run_cmd_as_user(traf_user, 'cat ~/.ssh/id_rsa.pub > ~/.ssh/authorized_keys')
    os.chmod(auth_key_file, 644)

    ssh_cfg_file = '%s/.ssh.config' % traf_user
    ssh_cfg = 'StrictHostKeyChecking=no\nNoHostAuthenticationForLocalhost=yes\n'
    with open(ssh_cfg_file, 'w') as f:
        f.write(ssh_cfg)
    os.chmod(ssh_cfg_file, 600)

    # set bashrc
    # TODO: set real SQ_HOME
    sq_home = traf_home_dir + 'trafodion-2.0'
    change_items = {'sq_home': sq_home, 'node_list':dbcfgs['node_list'], 'my_nodes':dbcfgs['my_nodes']}

    bashrc_template = '%s/bashrc.template' % TMP_FOLDER
    mod_template(bashrc_template, change_items)
        
    # backup bashrc if exsits

    # copy bashrc to trafodion's home
    run_cmd('cp %s/bashrc.template %s/.bashrc' % (TMP_FOLDER, traf_user_dir))
    run_cmd('chown -R %s:%s %s/.bashrc' % (traf_user, traf_group, traf_user_dir))

    # set ulimits for trafodion user
    ulimits_file = '/etc/security/limits.d/%s.conf' % traf_user
    ulimits_config = '\
# Trafodion settings\n\
%s   soft   core unlimited\n\
%s   hard   core unlimited\n\
%s   soft   memlock unlimited\n\
%s   hard   memlock unlimited\n\
%s   soft   nofile 32768\n\
%s   hard   nofile 65536\n\
%s   soft   nproc 100000\n\
%s   hard   nproc 100000\n\
%s   soft nofile 8192\n\
%s   hard nofile 65535\n\
hbase soft nofile 8192' % ((traf_user,) * 10)
    with open(ulimits_file, 'w') as f:
        f.write(ulimits_config)

# main
run()
