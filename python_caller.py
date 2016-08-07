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
        self.rc = 0
        self.chkssh_cmd = 'exit 0'
        self.tmp_folder = '.install'
        self.sshpass = self.__sshpass_available()

    def __commands(self, method):
        """ create 'ssh' or 'scp' commands """
        cmd = []
        if self.sshpass and self.pwd: cmd = ['sshpass','-p', self.pwd]
        cmd += [method]
        if not self.pwd: cmd += ['-oPasswordAuthentication=no']
        return cmd
        
    def __put_file(self, src_file, dest_file=''):
        if not os.path.exists(src_file):
            err('Script %s doesn\'t exist' % src_file)
        if not dest_file: dest_file = src_file

        cmd = self.__commands('scp')
        cmd += [src_file]
        cmd += ['%s:~/%s/%s' % (self.host, self.tmp_folder, dest_file)]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.communicate()
        except Exception as e:
            err('Failed to copy file to remote host: %s' %  e)

    def run_script(self, script_file, script_options='', verbose=False):

        # check host connectivity first
        self.__run_sshcmd(self.chkssh_cmd)

        # create tmp folder
        self.__run_sshcmd('mkdir -p ~/%s' % self.tmp_folder)

        # copy file to remote
        target_file = script_file.split('/')[-1]
        self.__put_file(script_file, target_file)
        self.__put_file('common.py')

        # set permission
        self.__run_sshcmd('chmod a+rx %s/%s' % (self.tmp_folder, target_file))

        # run script
        cmd = '~/%s/%s' % (self.tmp_folder, target_file)
        if script_options: cmd += ' ' + script_options 
        output = self.__run_sshcmd(cmd)
        if verbose: print output

        ok('Host [%s]: script \'%s\' running successfully!' % (self.host, script_file))

        #remove tmp folder
        self.__run_sshcmd('rm -rf %s' % self.tmp_folder)
            
        
    def __run_sshcmd(self, user_cmd):
        user_cmds = user_cmd.split()
        cmd = self.__commands('ssh')
        cmd += [self.host]
        cmd += user_cmds

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        self.rc = p.returncode
        if self.rc != 0:
            if user_cmd == self.chkssh_cmd:
                err('Host [%s]: Failed to connect using SSH! Check password or connectivity.' % (self.host))
            else:
                msg = 'Host [%s]: Failed to run \'%s\'' % (self.host, user_cmd.split('/')[-1])
                if stderr: msg += ': ' + stderr
                get_logger().error(msg)
                err(msg)
        return stdout


    def __sshpass_available(self):
        sshpass_available = True
        try:
            p = subprocess.Popen(['sshpass'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.communicate()
        except OSError:
            sshpass_available = False

        return sshpass_available

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
def run(cfgs, options):
    stat_file = 'install.status'
    cfg_file = 'script_config.json'

    conf = ParseJson(cfg_file).jload()
    script_cfgs = conf['conf']

    hosts = ['eason-1', 'eason-2']
    #hosts = ['esgvm-eason']
    local_host = socket.gethostname()

    # Check if install on localhost
    islocal = lambda h, lh: True if len(h) == 1 and (h[0] == 'localhost' or h[0] in lh) else False

    threshold = 10
    #enable_pwd = True
    enable_pwd = False
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
        status = Status(stat_file, script)
        if status.get_status(): 
            info('Script \'%s\' had already been executed, skipping ...' % script)
            continue

        if islocal(hosts, local_host):
            rc = run_cmd(sys.path[0] + '/' + script)
            if rc == 1: 
                msg = 'Failed to run \'%s\'' % script
                get_logger().error(msg)
                err(msg)
            else:
                ok('Script \'%s\' running successfully!' % script)
        else:
            if node == 'local':
                Remote(local_host, pwd).run_script(script)
            if node == 'first':
                remote_instances[0].run_script(script)
            elif node == 'all':
                # set thread count threshold 
                l = len(remote_instances)
                if l > threshold:
                    piece = (l - (l % threshold)) / threshold
                    parted_remote_instances = [remote_instances[threshold*i:threshold*(i+1)] for i in range(piece)]
                    parted_remote_instances.append(remote_instances[threshold*piece:])
                else:
                    parted_remote_instances = [remote_instances]

                for parted_remote_inst in parted_remote_instances:
                    threads = [Thread(target=r.run_script, args=(script, )) for r in parted_remote_inst]
                    for t in threads: t.start()
                    for t in threads: t.join()
                    if sum([ r.rc for r in parted_remote_inst ]) != 0:
                        err('Script failed to run on one or more nodes, exiting ...')

        status.set_status()
    
    # remove status file if all scripts run successfully
    os.remove(stat_file)


if __name__ == '__main__':
    run(1,1)
    exit(0)
