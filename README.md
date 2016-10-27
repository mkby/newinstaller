# Apache Trafodion Python Installer

## Prerequisite:

- CDH/HDP is installed on Trafodion nodes with web UI enabled, or Apache Hadoop, HBase is installed on the same directory on all nodes
- /etc/hosts contains hostname info for all Trafodion nodes on installer's node
- python version 2.6/2.7, and python library `httplib2`, `prettytable`
- Trafodion server package file is stored on installer's node

> **installer node** can be any nodes as long as it can ssh to Trafodion nodes, it also can be one of the Trafodion nodes

## How to use:
- Two ways:
 - Simply invoke `./db_install.py` to start the installation in guided mode
 - Copy the `db_config_default` file to `your_db_config` and modify it, then invoke `./db_config.py --config-file your_db_config` to start installation in config mode
- For a quick install, you only need to put Trafodion package file in installer's directory, provide CDH/HDP web URL in `your_db_config` file and then it's ready to go!
- Use `./db_install.py --help` for more options
