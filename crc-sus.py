#!/usr/bin/env /absolute/path/to/py_wrap.sh
''' crc-sus.py -- Get SUs from crc-bank.db
Usage:
    crc-sus.py <account> 
    crc-sus.py -h | --help
    crc-sus.py -v | --version

Positional Arguments:
    <account>       The Slurm account

Options:
    -h --help                       Print this screen and exit
    -v --version                    Print the version of crc-sus.py
'''


# Test:
# 1. Make sure item exists
def check_item_in_table(table, account):
    if table.find_one(account=account) is None:
        exit("ERROR: The account: {0} doesn't appear to exist".format(account))

# Constants/Parameters, modify these
DATABASE = '/abolute/path/to/crc-bank.db'

import dataset
from docopt import docopt

# The magical mystical docopt line
arguments = docopt(__doc__, version='crc-sus.py version 0.0.1')

# Connect to the database and get the limits table
# Absolute path ////
db = dataset.connect('sqlite:///{0}'.format(DATABASE))
table = db['crc']

# Check that account exists
check_item_in_table(table, arguments['<account>'])

# Print out SUs
string = "Account {0} has {1} SUs"
sus = table.find_one(account=arguments['<account>'])['su_limit_hrs']
print(string.format(arguments['<account>'], sus))
