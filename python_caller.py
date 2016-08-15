#!/usr/bin/env python

from common import *
from threading import Thread
import subprocess
import getpass
import os, socket

class Remote:
    """ run commands or scripts remotely using ssh """
    def __init__(self, host, pwd):
        self.host = host
        self.pwd = pwd
        self.rc = 0 # multithread return code check
        self.tmp_folder = '.install'
        self.dbcfg_file = 'db_config'
        self.common_lib = 'common.py'
        self.sshpass = self.__sshpass_available()

    def __commands(self, method):
        """ create 'ssh' or 'scp' commands """
        cmd = []
        if self.sshpass and self.pwd: cmd = ['sshpass','-p', self.pwd]
        cmd += [method]
        if not self.pwd: cmd += ['-oPasswordAuthentication=no']
        return cmd
        
    def __put_file(self, *src_files):
        for src_file in src_files:
            if not os.path.exists(src_file):
                err('Script %s doesn\'t exist' % src_file)

        cmd = self.__commands('scp')
        cmd += ['-r']
        cmd += list(src_files)
        cmd += ['%s:~/%s/' % (self.host, self.tmp_folder)]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.communicate()
        except Exception as e:
            err('Failed to copy files to remote host: %s' %  e)

    def run_script(self, script_file, script_options='', verbose=False):

        # create tmp folder
        self.__run_sshcmd('mkdir -p ~/%s' % self.tmp_folder)

        # copy file to remote
        self.__put_file(script_file, self.dbcfg_file, self.common_lib)

        # set permission
        self.__run_sshcmd('chmod a+rx %s/%s' % (self.tmp_folder, script_file))

        # run script
        self.__run_script(script_file, script_options, verbose=verbose)

        #remove tmp folder
        self.__run_sshcmd('rm -rf %s' % self.tmp_folder)
            
    def __run_sshcmd(self, user_cmd):
        """ run internal used ssh command """
        user_cmds = user_cmd.split()
        cmd = self.__commands('ssh')
        cmd += [self.host]
        cmd += user_cmds

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        self.rc = p.returncode
        if self.rc != 0:
            msg = 'Host [%s]: Failed to run setup commands, check SSH password or connectivity' % self.host
            if stderr: msg += ': ' + stderr
            get_logger().error(msg)
            err(msg)
        
    def __run_script(self, script, script_options, verbose=False):
        script_cmd = 'cd ~/%s;./%s' % (self.tmp_folder, script)
        if script_options: script_cmd += ' ' + script_options 
        script_cmd = script_cmd.split()
        cmd = self.__commands('ssh')
        cmd += [self.host]
        cmd += script_cmd

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        self.rc = p.returncode

        get_logger().info(' Host [%s]: %s' % (self.host, stdout))
        if verbose: print stdout

        if self.rc == 0:
            state_ok('Host [%s], Script [%s]' % (self.host, script))
        else:
            state_fail('Host [%s], Script [%s]' % (self.host, script))
            msg = 'Host [%s]: Failed to run \'%s\'' % (self.host, script)
            if stderr: 
                msg += ': ' + stderr
                print stderr
            get_logger().error(msg)
            exit(1)


    def __sshpass_available(self):
        sshpass_available = True
        try:
            p = subprocess.Popen(['sshpass'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.communicate()
        except OSError:
            sshpass_available = False

        return sshpass_available

def state_ok(msg):
    state(32, ' OK ', msg)

def state_fail(msg):
    state(31, 'FAIL', msg)

def state_skip(msg):
    state(33, 'SKIP', msg)

def state(color, result, msg):
    WIDTH = 80
    print '\33[%dm%s %s [ %s ]\33[0m\n' % (color, msg, (WIDTH - len(msg))*'.', result)

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
    enable_pwd = True
    if enable_pwd and not islocal(hosts, local_host):
        pwd = getpass.getpass('Input SSH Password: ')
    else:
        pwd = ''

    remote_instances = []
    if not islocal(hosts, local_host):
        remote_instances = [Remote(host, pwd) for host in hosts]

    for cfg in script_cfgs:
        script = cfg['script']
        node = cfg['node']
        status = Status(STAT_FILE, script)
        if status.get_status(): 
            state_skip('Script [%s] had already been executed' % script)
            continue

        # install on localhost only
        if islocal(hosts, local_host):
            rc = run_cmd(sys.path[0] + '/' + script)
            if rc != 0: 
                get_logger().error('Failed to run \'%s\'' % script)
                state_fail('Script [%s]' % script)
            else:
                state_ok('Script [%s]' % script)
        else:
            if node == 'local':
                Remote(local_host, pwd).run_script(script)
            elif node == 'first':
                #remote_instances[0].run_script(script)
                remote_instances[0].run_script(script, verbose=True)
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
                    if sum([ r.rc for r in parted_remote_inst ]) != 0:
                        err('Script failed to run on one or more nodes, exiting ...')
            else:
                # should not go to here
                err('Invalid configuration for %s' % cfg_file)

        status.set_status()
    
    # remove status file if all scripts run successfully
    os.remove(stat_file)


if __name__ == '__main__':
    run(1,1)
    exit(0)
