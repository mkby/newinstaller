#!/usr/bin/env python
import os
import sys
import json
import re
import time
import base64
# httplib2 is not installed by default
try:
    import httplib2
except ImportError:
    print 'Python module httplib2 is not found. Install python-httplib2 first.'
    exit(1)
from ConfigParser import ConfigParser
from collections import defaultdict

__version__ = 'v1.0.0'
installer_loc = sys.path[0]

def version():
    print 'Installer version: %s' % __version__
    exit(0)

def ok(msg):
    print '\n\33[32m***[OK]: %s \33[0m' % msg

def info(msg):
    print '\n\33[33m***[INFO]: %s \33[0m' % msg

def err(msg):
    print '\n\33[31m***[ERROR]: %s \33[0m' % msg
    exit(1)

class HttpGet:
    def __init__(self, user, passwd):
        self.user = user
        self.passwd = passwd
        self.h = httplib2.Http(disable_ssl_certificate_validation=True)  
        self.h.add_credentials(self.user, self.passwd)
        self.headers = {}
        self.headers['X-Requested-By'] = 'trafodion'
        self.headers['Content-Type'] = 'application/json'
        self.headers['Authorization'] = 'Basic %s' % (base64.b64encode('%s:%s' % (self.user, self.passwd)))

    def get_content(self, url):
        self.url = url
        try:
            resp, content = self.h.request(self.url, 'GET', headers=self.headers)  
            if resp.status != 200:
                err('Error return code %s when getting configs from manager URL' % resp.status)
        except Exception:
            err('Failed to access manager URL ' + url)

        try:
            return defaultdict(str, json.loads(content))
        except ValueError:
            err('Failed to get data from manager URL, check if password is correct')

class ParseJson:
    """ 
    jload: load json file to a dict
    jsave: save dict to json file with pretty format
    """
    def __init__(self, js_file):
        self.js_file = js_file

    def jload(self):
        with open(self.js_file, 'r') as f:
            tmparray = f.readlines()
        content = ''
        for t in tmparray:
            content += t

        try:
            return defaultdict(str, json.loads(content))
        except ValueError:
            err('No json format found in config file')

    def jsave(self, dic):
        with open(self.js_file, 'w') as f:
            f.write(json.dumps(dic, indent=4))

class ParseIni:
    def __init__(self):
        self.cfg_file = 'config.ini'
        self.conf = ConfigParser()
        self.conf.read(self.cfg_file)

    def get_hosts(self):
        try:
            host_content = self.conf.items('hosts')[0][1]
            return expNumRe(host_content)
        except IndexError:
            err('Failed to parse hosts from %s' % self.cfg_file)

    def get_roles(self):
        try:
            return [ [i[0],i[1].split(',')] for i in self.conf.items('roles') ]
        except:
            return []

    def _get_dir(self, dir_name):
        try:
            return [c[1] for c in self.conf.items('dirs') if c[0] == dir_name][0]
        except:
            return ''

    def get_repodir(self):
        return self._get_dir('repo_dir')

    def get_parceldir(self):
        return self._get_dir('parcel_dir')

    
def http_start(repo_dir, repo_port):
    info('Starting temporary python http server')
    os.system("cd %s; python -m SimpleHTTPServer %s > /dev/null 2>&1 &" % (repo_dir, repo_port))

def http_stop():
    info('Stopping temporary python http server')
    os.system("ps -ef|grep SimpleHTTPServer |grep -v grep | awk '{print $2}' |xargs kill -9")


def set_ansible_cfgs(host_content):
    ts = time.strftime('%y%m%d_%H%M')
    logs_dir = installer_loc + '/logs'
    hosts_file = installer_loc + '/hosts'
    if not os.path.exists(logs_dir): os.mkdir(logs_dir)
    log_path = '%s/%s_%s.log' %(logs_dir, sys.argv[0].split('/')[-1].split('.')[0], ts)

    ansible_cfg = os.getenv('HOME') + '/.ansible.cfg'
    content = '[defaults]\n'
    content += 'log_path = %s\n' % log_path
    content += 'inventory =' + hosts_file + '\n'
    content += 'host_key_checking = False\n'
#    content += 'display_skipped_hosts = False\n'
    def write_file(filename, content):
        try:
            with open(filename, 'w') as f:
                f.write(content)
        except IOError:
            err('Failed to open %s file' % filename)
    write_file(ansible_cfg, content)
    write_file(hosts_file, host_content)
    
    return log_path

def format_output(text):
    num = len(text) + 4
    print '*' * num
    print '  ' + text
    print '*' * num

def expNumRe(text):
    """
    expand numeric regular expression to list
    e.g. 'n[01-03],n1[0-1]': ['n01','n02','n03','n10','n11']
    e.g. 'n[09-11].com': ['n09.com','n10.com','n11.com']
    """
    explist = []
    for regex in text.split(','):
        regex = regex.strip()
        r = re.match(r'(.*)\[(\d+)-(\d+)\](.*)',regex)
        if r:
            h = r.group(1)
            d1 = r.group(2)
            d2 = r.group(3)
            t = r.group(4)

            convert = lambda d: str(('%0' + str(min(len(d1), len(d2))) + 'd') % d)
            if d1 > d2: d1,d2 = d2,d1
            explist.extend([h + convert(c) + t for c in range(int(d1), int(d2)+1)])

        else:
            # keep original value if not matched
            explist.append(regex)

    return explist

def time_elapse(func):
    """ time elapse decorator """
    def wrapper(*args):
        start_time = time.time()
        func(*args)
        end_time = time.time()
        seconds = end_time - start_time
        hours = seconds / 3600
        seconds = seconds % 3600
        minutes = seconds / 60
        seconds = seconds % 60
        print '\nInstallation time: %d hour(s) %d minute(s) %d second(s)' % (hours, minutes, seconds)
    return wrapper

if __name__ == "__main__":
    exit(0)
