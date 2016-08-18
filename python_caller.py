#!/usr/bin/env python

import os
import subprocess
import getpass
import socket
from threading import Thread
from common import *

class RemoteRun(Remote):
    """ run commands or scripts remotely using ssh """

    def __init__(self, host, user='', pwd=''):
        super(RemoteRun, self).__init__(host, user, pwd)
        self.rc = 0 # multithread return code check
        self.tmp_folder = '.install'
        self.common_lib = 'common.py'

    def run_script(self, script_file, script_options='', verbose=False):

        begin(script_file, self.host)
        # create tmp folder
        self.__run_sshcmd('mkdir -p ~/%s' % self.tmp_folder)

        # copy file to remote
        self.copy([script_file, DBCFG_FILE, self.common_lib], remote_folder=self.tmp_folder)

        # set permission
        self.__run_sshcmd('chmod a+rx %s/%s' % (self.tmp_folder, script_file))

        # run script
        self.__run_script(script_file, script_options, verbose=verbose)

        #remove tmp folder
        self.__run_sshcmd('rm -rf %s' % self.tmp_folder)
            
    def __run_ssh(self, user_cmd):
        user_cmds = user_cmd.split()

        cmd = self._commands('ssh')
        if self.user: 
            cmd += ['%s@%s' % (self.user, self.host)]
        else:
            cmd += [self.host]
        cmd += user_cmds

        return self._execute(cmd)

    def __run_sshcmd(self, int_cmd):
        """ run internal used ssh command """

        self.rc, stdout, stderr = self.__run_ssh(int_cmd)
        if self.rc != 0:
            msg = 'Host [%s]: Failed to run setup commands, check SSH password or connectivity' % self.host
            if stderr: msg += '\nReason: ' + stderr
            get_logger().error(msg)
            err(msg)
        
    def __run_script(self, script, script_options, verbose=False):
        script_cmd = 'cd ~/%s;./%s' % (self.tmp_folder, script)
        if script_options: script_cmd += ' ' + script_options 

        self.rc, stdout, stderr = self.__run_ssh(script_cmd)

        get_logger().info(' Host [%s]: %s' % (self.host, stdout))
        if verbose: print stdout

        if self.rc == 0:
            state_ok('Host [%s]: Script [%s]' % (self.host, script))
        else:
            state_fail('Host [%s]: Script [%s]' % (self.host, script))
            msg = 'Host [%s]: Failed to run \'%s\'' % (self.host, script)
            if stderr: 
                msg += ': ' + stderr
                print stderr
            get_logger().error(msg)
            exit(1)


def state_ok(msg):
    state(32, ' OK ', msg)

def state_fail(msg):
    state(31, 'FAIL', msg)

def state_skip(msg):
    state(33, 'SKIP', msg)

def state(color, result, msg):
    WIDTH = 80
    print '\33[%dm%s %s [ %s ]\33[0m\n' % (color, msg, (WIDTH - len(msg))*'.', result)

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
        remote_instances = [RemoteRun(host, pwd) for host in hosts]

    
    def run_local_script(script):
        # copy file needs to use SSH to login remote nodes,
        # so pass the ssh password to this sub script if have
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
            get_logger().error(msg)
            state_fail('localhost: Script [%s]' % script)
            exit(rc)
        else:
            state_ok('Script [%s]' % script)

    # run sub scripts
    try:
        for cfg in script_cfgs:
            script = cfg['script']
            node = cfg['node']
            status = Status(STAT_FILE, script)
            if status.get_status(): 
                state_skip('Script [%s] had already been executed' % script)
                continue

            # if install on localhost only
            if islocal(hosts, local_host):
                run_local_script(script)
            else:
                if node == 'local':
                    run_local_script(script)
                elif node == 'first':
                    #remote_instances[0].run_script(script)
                    remote_instances[0].run_script(script, verbose=True)
                elif node == 'all':
                    # set thread count threshold 
                    THRESHOLD = 5
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
            status.set_status()
    except KeyboardInterrupt:
        err('User quit')

    
    # remove status file if all scripts run successfully
    os.remove(STAT_FILE)


if __name__ == '__main__':
    run(1,1)
    exit(0)
