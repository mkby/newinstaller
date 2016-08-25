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

    traf_home = cmd_output('sudo cat /etc/default/useradd |grep HOME |cut -d "=" -f 2')[0].strip()
    traf_user_dir = '/%s/%s' % (traf_home, traf_user)

    # create trafodion user and group
    if not cmd_output('getent passwd %s' % traf_user)[0]:
        run_cmd('sudo useradd --shell /bin/bash -m %s -g %s --password "$(openssl passwd %s)"' % (traf_user, traf_group, traf_pwd))

    if not cmd_output('getent group %s' % traf_user)[0]:
        run_cmd('sudo groupadd %s > /dev/null 2>&1' % traf_user)
    

    # set ssh key
    run_cmd_as_user(traf_user, 'echo -e "y" | ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa')
    # the key is generated in another script running on the installer node
    run_cmd('sudo cp ~/id_rsa* %s/.ssh/' % traf_user_dir)
    run_cmd('sudo chown -R %s:%s %s/.ssh/' % (traf_user, traf_group, traf_user_dir))

    run_cmd_as_user(traf_user, 'cat ~/.ssh/id_rsa.pub > ~/.ssh/authorized_keys')
    run_cmd_as_user(traf_user, 'chmod 644 ~/.ssh/authorized_keys')

    run_cmd_as_user(traf_user, 'echo -e "StrictHostKeyChecking=no\nNoHostAuthenticationForLocalhost=yes\n" > ~/.ssh/config')
    run_cmd_as_user(traf_user, 'chmod 600 ~/.ssh/config')

    # set bashrc
    # TODO: set real SQ_HOME
    change_items = {'sq_home': '/home/trafodion/testing', 'node_list':dbcfgs['node_list'], 'my_nodes':dbcfgs['my_nodes']}

    bashrc_template = '%s/bashrc.template' % TMP_FOLDER
    mod_template(bashrc_template, change_items)
        
    # copy bashrc to trafodion's home
    run_cmd('sudo cp %s/bashrc.template %s/.bashrc' % (TMP_FOLDER, traf_user_dir))
    run_cmd('sudo chown -R %s:%s %s/.bashrc' % (traf_user, traf_group, traf_user_dir))

# main
run()
