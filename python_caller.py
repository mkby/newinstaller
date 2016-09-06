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

import os
import time
import subprocess
import getpass
import socket
from glob import glob
from threading import Thread
from common import *

THRESHOLD = 10 # thread count
LOG_FILE = '%s/logs/install_%s.log' % (INSTALLER_LOC, time.strftime('%Y%m%d_%H%M'))
logger = get_logger(LOG_FILE)

class RemoteRun(Remote):
    """ run commands or scripts remotely using ssh """

    def __init__(self, host, user='', pwd=''):
        super(RemoteRun, self).__init__(host, user, pwd)

        # create tmp folder
        self.__run_sshcmd('mkdir -p %s' % TMP_DIR)

        # copy all needed files to remote host
        all_files = glob(INSTALLER_LOC + '/*.py') + glob(INSTALLER_LOC + '/*.json') + \
                    glob(INSTALLER_LOC + '/*.sh') + glob(INSTALLER_LOC + '/*.template')

        self.copy(all_files, remote_folder=TMP_DIR)

        # set permission
        self.__run_sshcmd('chmod a+rx %s/*.py' % TMP_DIR)

    def __del__(self):
        # clean up
        self.__run_ssh('sudo rm -rf %s' % TMP_DIR)

    def run_script(self, script, run_user, json_string, verbose=False):
        """ @param run_user: run the script with this user """

        if run_user:
            # format string in order to run with 'sudo su $user -c $cmd'
            json_string = json_string.replace('"','\\\\\\"').replace(' ','').replace('{','\\{')
            # this command only works with shell=True
            script_cmd = '"sudo su - %s -c \'%s/%s %s\'"' % (run_user, TMP_DIR, script, json_string)
            self.__run_ssh(script_cmd, verbose=verbose, shell=True)
        else:
            script_cmd = 'sudo %s/%s \'%s\'' % (TMP_DIR, script, json_string)
            self.__run_ssh(script_cmd, verbose=verbose)

        format1 = 'Host [%s]: Script [%s]: %s' % (self.host, script, self.stdout)
        format2 = 'Host [%s]: Script [%s]' % (self.host, script)

        logger.info(format1)

        if self.rc == 0:
            state_ok(format2)
            logger.info(format2 + ' ran successfully!')
        else:
            state_fail(format2)
            msg = 'Host [%s]: Failed to run \'%s\'' % (self.host, script)
            if self.stderr: 
                msg += ': ' + self.stderr
                print '\nReason: ' + self.stderr
            logger.error(msg)
            exit(1)

    def __run_ssh(self, user_cmd, verbose=False, shell=False):
        """ @params: user_cmd should be a string """
        cmd = self._commands('ssh')
        cmd += ['-tt'] # force tty allocation
        if self.user: 
            cmd += ['%s@%s' % (self.user, self.host)]
        else:
            cmd += [self.host]

        # if shell=True, cmd should be a string not list
        if shell: 
            cmd = ' '.join(cmd) + ' '
            cmd += user_cmd
        else:
            cmd += user_cmd.split()

        self._execute(cmd, verbose=verbose, shell=shell)

    def __run_sshcmd(self, int_cmd):
        """ run internal used ssh command """

        self.__run_ssh(int_cmd)
        if self.rc != 0:
            msg = 'Host [%s]: Failed to run internal commands, check SSH password or connectivity' % self.host
            logger.error(msg)
            err_m(msg)

def state_ok(msg):
    state(32, ' OK ', msg)

def state_fail(msg):
    state(31, 'FAIL', msg)

def state_skip(msg):
    state(33, 'SKIP', msg)

def state(color, result, msg):
    WIDTH = 80
    print '\n\33[%dm%s %s [ %s ]\33[0m\n' % (color, msg, (WIDTH - len(msg))*'.', result)

class Status:
    def __init__(self, stat_file, name):
        self.stat_file = stat_file
        self.name = name

    def get_status(self):
        if not os.path.exists(self.stat_file): os.mknod(self.stat_file)
        with open(self.stat_file, 'r') as f:
            st = f.readlines()
        for s in st:
            if s.split()[0] == self.name: return True
        return False

    def set_status(self):
        with open(self.stat_file, 'a+') as f:
            f.write('%s OK\n' % self.name)

@time_elapse
def run(dbcfgs, options, mode='install'):
    """ main entry
        mode: install/discover
    """
    STAT_FILE = mode + '.status'
    SCRCFG_FILE = 'script_config.json'

    verbose = True if options.verbose else False
    if options.pwd: enable_pwd = True
    if options.user: user = options.user
    if options.fork: THRESHOLD = options.fork

    conf = ParseJson(SCRCFG_FILE).jload()
    script_cfgs = conf[mode]

    dbcfgs_json = json.dumps(dbcfgs)
    hosts = dbcfgs['node_list'].split(',')
    local_host = socket.gethostname().split('.')[0]

    # Check if install on localhost
    islocal = lambda h, lh: True if len(h) == 1 and (h[0] == 'localhost' or h[0] == lh) else False

    # handle skipped scripts
    skipped_scripts = []
    
    # set skipped scripts which no need to run on an upgrade install
    if dbcfgs['upgrade'] == 'Y':
        skipped_scripts += ['hadoop_mods', 'traf_user', 'traf_dep']

    if dbcfgs['traf_start'] == 'N':
        skipped_scripts += ['traf_start']

    if 'APACHE' in dbcfgs['distro']:
        skipped_scripts += ['hadoop_mods']
    else:
        skipped_scripts += ['apache_mods', 'apache_restart']


    def run_local_script(script, json_string, req_pwd):
        cmd = '%s/%s \'%s\'' % (INSTALLER_LOC, script, json_string)

        # pass the ssh password to sub scripts which need SSH password
        if req_pwd: cmd += ' ' + pwd

        if verbose: print cmd

        # stdout on screen
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = p.communicate()

        rc = p.returncode
        if rc != 0:
            msg = 'Failed to run \'%s\'' % script
            if stderr: 
                msg += ': ' + stderr
                print stderr
            logger.error(msg)
            state_fail('localhost: Script [%s]' % script)
            exit(rc)
        else:
            state_ok('Script [%s]' % script)
            logger.info('Script [%s] ran successfully!' % script)

    
    # run sub scripts
    try:
        
        if enable_pwd and not islocal(hosts, local_host):
            pwd = getpass.getpass('Input SSH Password: ')
        else:
            pwd = ''

        remote_instances = []
        if not islocal(hosts, local_host):
            remote_instances = [RemoteRun(host, pwd=pwd) for host in hosts]

        logger.info(' ***** %s Start *****' % mode)
        for cfg in script_cfgs:
            script = cfg['script']
            node = cfg['node']
            run_user = ''
            if not 'run_as_traf' in cfg.keys():
                pass
            elif cfg['run_as_traf'] == 'yes':
                run_user = dbcfgs['traf_user']

            if not 'req_pwd' in cfg.keys():
                req_pwd = False
            elif cfg['req_pwd'] == 'yes':
                req_pwd = True

            status = Status(STAT_FILE, script)
            if status.get_status(): 
                msg = 'Script [%s] had already been executed' % script
                state_skip(msg)
                logger.info(msg)
                continue

            if script.split('.')[0] in skipped_scripts:
                continue
            else:
                print '\n*** Start running script [%s]:' % script

            # if install on localhost only
            if not remote_instances:
                run_local_script(script, dbcfgs_json, req_pwd)
            else:
                if node == 'local':
                    run_local_script(script, dbcfgs_json, req_pwd)
                elif node == 'first':
                    remote_instances[0].run_script(script, run_user, dbcfgs_json, verbose=verbose)
                elif node == 'all':
                    l = len(remote_instances)
                    if l > THRESHOLD:
                        piece = (l - (l % THRESHOLD)) / THRESHOLD
                        parted_remote_instances = [remote_instances[THRESHOLD*i:THRESHOLD*(i+1)] for i in range(piece)]
                        parted_remote_instances.append(remote_instances[THRESHOLD*piece:])
                    else:
                        parted_remote_instances = [remote_instances]

                    for parted_remote_inst in parted_remote_instances:
                        threads = [Thread(target=r.run_script, args=(script, run_user, dbcfgs_json, verbose)) for r in parted_remote_inst]
                        for t in threads: t.start()
                        for t in threads: t.join()

                        if sum([ r.rc for r in parted_remote_inst ]) != 0:
                            err_m('Script failed to run on one or more nodes, exiting ...\nCheck log file %s for details.' % LOG_FILE)
                else:
                    # should not go to here
                    err_m('Invalid configuration for %s' % SCRCFG_FILE)

            status.set_status()
    except KeyboardInterrupt:
        err_m('User quit')

    # remove status file if all scripts run successfully
    os.remove(STAT_FILE)

if __name__ == '__main__':
    cfgs = {'node_list': 'eason-1 eason-2'}
    run(cfgs, 1)
    exit(0)
