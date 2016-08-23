#!/usr/bin/env python

import os
import subprocess
import getpass
import socket
from glob import glob
from threading import Thread
from common import *

logger = get_logger()
class RemoteRun(Remote):
    """ run commands or scripts remotely using ssh """

    def __init__(self, host, user='', pwd=''):
        super(RemoteRun, self).__init__(host, user, pwd)
        self.tmp_folder = '.install'

        # create tmp folder
        self.__run_sshcmd('mkdir -p ~/%s' % self.tmp_folder)

        # copy all needed files to remote host
        all_files = glob(INSTALLER_LOC + '/*.py') + glob(INSTALLER_LOC + '/*.json') + glob(INSTALLER_LOC + '/*.sh')
        self.copy(all_files, remote_folder=self.tmp_folder)

        # set permission
        self.__run_sshcmd('chmod a+rx %s/*.py' % self.tmp_folder)

    def __del__(self):
        # clean up
        self.__run_ssh('rm -rf ~/%s' % self.tmp_folder)

    def run_script(self, script, script_options='', verbose=False):

        begin(script, self.host)
        script_cmd = '~/%s/%s' % (self.tmp_folder, script)
        if script_options: script_cmd += ' ' + script_options 

        self.__run_ssh(script_cmd, tty=True)

        format1 = 'Host [%s]: Script [%s]: %s' % (self.host, script, self.stdout)
        format2 = 'Host [%s]: Script [%s]' % (self.host, script)

        logger.info(format1)
        if verbose: print format1

        if self.rc == 0:
            state_ok(format2)
        else:
            state_fail(format2)
            msg = 'Host [%s]: Failed to run \'%s\'' % (self.host, script)
            if self.stderr: 
                msg += ': ' + self.stderr
                print '\nReason: ' + self.stderr
            logger.error(msg)
            exit(1)

    def __run_ssh(self, user_cmd, tty=False):
        user_cmds = user_cmd.split()

        cmd = self._commands('ssh')
        if tty: cmd += ['-tt'] # force tty allocation
        if self.user: 
            cmd += ['%s@%s' % (self.user, self.host)]
        else:
            cmd += [self.host]
        cmd += user_cmds

        self._execute(cmd)

    def __run_sshcmd(self, int_cmd):
        """ run internal used ssh command """

        self.__run_ssh(int_cmd)
        if self.rc != 0:
            msg = 'Host [%s]: Failed to run internal commands, check SSH password or connectivity' % self.host
            if self.stderr: msg += '\nReason: ' + self.stderr
            logger.error(msg)
            err(msg)

def state_ok(msg):
    state(32, ' OK ', msg)

def state_fail(msg):
    state(31, 'FAIL', msg)

def state_skip(msg):
    state(33, 'SKIP', msg)

def state(color, result, msg):
    WIDTH = 80
    print '\n\33[%dm%s %s [ %s ]\33[0m\n' % (color, msg, (WIDTH - len(msg))*'.', result)

def begin(script, host=''):
    output = '\nStart running script [%s]' % script
    if host: 
        output += ' on host [%s]' % host
    else:
        output += ' on localhost'

    print output

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
def run(dbcfgs, options):
    """ main entry """
    STAT_FILE = 'install.status'
    SCRCFG_FILE = 'script_config.json'

    conf = ParseJson(SCRCFG_FILE).jload()
    script_cfgs = conf['conf']

    hosts = ['centosha-2', 'eason-2']
    #hosts = dbcfgs['node_list'].split()
    local_host = socket.gethostname().split('.')[0]

    # Check if install on localhost
    islocal = lambda h, lh: True if len(h) == 1 and (h[0] == 'localhost' or h[0] == lh) else False

    #enable_pwd = False
    #if options.pwd: enable_pwd = True
    #if options.user: user = options.user
    #if options.nomod: nomod = True
    #if options.fork: THRESHOLD = options.fork
    enable_pwd = True
    if enable_pwd and not islocal(hosts, local_host):
        pwd = getpass.getpass('Input SSH Password: ')
    else:
        pwd = ''

    remote_instances = []
    if not islocal(hosts, local_host):
        remote_instances = [RemoteRun(host, pwd=pwd) for host in hosts]

    
    def run_local_script(script):
        # pass the ssh password to sub scripts which need SSH
        #TODO: not finished
        if script:
            cmd = sys.path[0] + '/' + script + ' ' + pwd
        else:
            cmd = sys.path[0] + '/' + script

        begin(script)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
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

    # run sub scripts
    try:
        logger.info(' ***** Install Start *****')
        for cfg in script_cfgs:
            script = cfg['script']
            node = cfg['node']
            status = Status(STAT_FILE, script)
            if status.get_status(): 
                state_skip('Script [%s] had already been executed' % script)
                continue

            # if install on localhost only
            if not remote_instances:
                run_local_script(script)
            else:
                if node == 'local':
                    run_local_script(script)
                elif node == 'first':
                    remote_instances[0].run_script(script)
                elif node == 'all':
                    # set thread count threshold 
                    THRESHOLD = 10
                    l = len(remote_instances)
                    if l > THRESHOLD:
                        piece = (l - (l % THRESHOLD)) / THRESHOLD
                        parted_remote_instances = [remote_instances[THRESHOLD*i:THRESHOLD*(i+1)] for i in range(piece)]
                        parted_remote_instances.append(remote_instances[THRESHOLD*piece:])
                    else:
                        parted_remote_instances = [remote_instances]

                    for parted_remote_inst in parted_remote_instances:
                        threads = [Thread(target=r.run_script, args=(script, )) for r in parted_remote_inst]
                        for t in threads: t.start()
                        for t in threads: t.join()
                        #TODO: add log file location to display, log file name reconsider
                        if sum([ r.rc for r in parted_remote_inst ]) != 0:
                            err('Script failed to run on one or more nodes, exiting ...')
                else:
                    # should not go to here
                    err('Invalid configuration for %s' % SCRCFG_FILE)

    #        # cleanup install files on all nodes
    #        if remote_instances:
    #            threads = [Thread(target=r.clean) for r in remote_instances]
    #            for t in threads: t.start()
    #            for t in threads: t.join()

            status.set_status()
    except KeyboardInterrupt:
        err('User quit')

    # remove status file if all scripts run successfully
    os.remove(STAT_FILE)

if __name__ == '__main__':
    run(1,1)
    exit(0)
