#!/usr/bin/env python

from common import ParseJson, ok, err, info, time_elapse
from threading import Thread
import subprocess
import getpass
import os, socket

class Remote:
    ''' run commands or scripts remotely using ssh '''
    def __init__(self, host):
        self.host = host
        self.pwd = ''


    def __put_file(self, src_file, dest_file):
        if not os.path.exists(src_file):
            err('Script %s doesn\'t exist' % src_file)
        cmd = []
        if sshpass_available() and self.pwd: cmd = ['sshpass','-p', self.pwd]
        cmd += ['scp']
        cmd += [src_file]
        cmd += ['%s:~/%s' % (self.host, dest_file)]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.communicate()
        except Exception as e:
            err('Failed to copy file to remote host: %s' %  e)

    def run_script(self, script_file, pwd='', script_options='', verbose=False):
        self.pwd = pwd

        # copy file to remote
        target_file = '.' + script_file.split('/')[-1]
        self.__put_file(script_file, target_file)

        # set permission
        self.run_cmd('chmod a+rx ' + target_file)
        cmd = '~/' + target_file + ' ' + script_options
        output = self.run_cmd(cmd)
        if verbose: print output

        ok('Host [%s]: script \'%s\' running successfully!' % (self.host, script_file))
        #remove tmp file
        self.run_cmd('rm -rf ' + target_file)
            
        
    def run_cmd(self, user_cmd):
        user_cmds = user_cmd.split()
        cmd = []
        if sshpass_available() and self.pwd: cmd = ['sshpass','-p', self.pwd]
        cmd += ['ssh']
        cmd += ['-q', '-oStrictHostKeyChecking=no']
        cmd += [self.host]
        # issue on sh -c command to run 'hostname -s' 
        #cmd += ['sh', '-c']
        cmd += user_cmds

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout = p.communicate()[0]
        if p.returncode != 0:
            err('Host [%s]: Failed to run command: %s' % (self.host, user_cmd))
        return stdout


def sshpass_available():
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
    #if sshpass_available() and not options['pwd']:
    if sshpass_available():
        pwd = getpass.getpass('Input SSH Password: ')

    conf = ParseJson(cfg_file).jload()
    script_cfgs = conf['conf']

    hosts = ['cent-1']
    remote_instances = [Remote(host) for host in hosts]

    # TODO: run host checking first
    
    for cfg in script_cfgs:
        script = cfg['script']
        node = cfg['node']
        status = Status(stat_file, script)
        if status.get_status(): 
            info('Script \'%s\' had already been executed, skipping ...' % script)
            continue

        if node == 'local':
            Remote(socket.gethostname()).run_script(script, pwd)
        if node == 'first':
            Remote(hosts[0]).run_script(script, pwd)
        elif node == 'all':
            threads = [Thread(target=r.run_script, args=(script, pwd)) for r in remote_instances]
            # TODO: thread return code
            for t in threads: t.start()
            for t in threads: t.join()

        status.set_status()
    
    # remove status file if all scripts run successfully
    os.remove(stat_file)


if __name__ == '__main__':
    run(1,1)
    exit(0)
