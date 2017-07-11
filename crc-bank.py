#!/usr/bin/env /absolute/path/to/py_wrap.sh
''' crc-bank.py -- Deal with crc-bank.db
Usage:
    crc-bank.py insert <account> <su_limit_hrs>
    crc-bank.py modify <account> <su_limit_hrs>
    crc-bank.py add <account> <su_limit_hrs>
    crc-bank.py get_sus <account> 
    crc-bank.py check_service_units_limit <account> 
    crc-bank.py check_end_of_date_limit <account> 
    crc-bank.py reset_usage <account> 
    crc-bank.py release_hold <account> 
    crc-bank.py three_month_check <account> 
    crc-bank.py dump <filename>
    crc-bank.py repopulate <filename>
    crc-bank.py -h | --help
    crc-bank.py -v | --version

Positional Arguments:
    <account>       The Slurm account
    <su_limit_hrs>  The limit in CPU Hours (e.g. 10,000)
    <filename>      Dump to or repopulate from file, format is JSON

Options:
    -h --help                       Print this screen and exit
    -v --version                    Print the version of crc-bank.py
'''

# Constants/Parameters, modify these
CLUSTERS = ['cluster']
LOGFILE = '/absolute/path/to/crc-bank.log'
DATABASE = '/abolute/path/to/crc-bank.db'

# Test:
# 1. Is the number of service units really an integer?
# 2. Is the number of service units greater than the default?
def check_service_units(given_integer):
    try:
        service_units = int(given_integer)
        if service_units == -1:
            print("WARNING: Giving the group infinite SUs")
        elif service_units < 10000:
            exit("ERROR: Number of SUs => {0} is too small!".format(service_units))
        return service_units
    except ValueError:
        exit("ERROR: The given limit => {0} is not an integer!".format(given_integer))


# Test:
# 1. Does association for account and all clusters exists in Slurm database?
def check_account_and_cluster(account):
    for cluster in CLUSTERS:
        command = "sacctmgr -n show assoc account={0} cluster={1} format=account,cluster"
        check_string = popen(command.format(account, cluster)).read().split('\n')[0]
        if check_string.strip() == "":
            exit("ERROR: no association for account {0} on cluster {1}".format(account, cluster))


# Test:
# 1. On insert, does item already exist in the database?
def check_insert_item_in_table(table, account):
    if not table.find_one(account=account) is None:
        exit("ERROR: Account {0} already exists in database, did you want to modify it?".format(account))


# Test:
# 1. On modify, make sure item exists
def check_item_in_table(table, account, mode):
    if table.find_one(account=account) is None:
        if mode == 'modify' or mode == 'check':
            exit("ERROR: Account {0} doesn't exists in database, did you want to insert it?".format(account))
        elif mode == 'reset_usage':
            exit("ERROR: Account {0} doesn't exists in database, you should create a limit before resetting?".format(account))


# Logging function
def log_action(string):
    with open(LOGFILE, 'a+') as f:
        f.write("{0}: {1}\n".format(datetime.now(), string))


import dataset
from docopt import docopt
# Default is python 2.6, can't use subprocess
from os import popen
from os.path import exists
from datetime import date, datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import json

# The magical mystical docopt line, options_first=True because su_limit_hrs can be negative!
arguments = docopt(__doc__, version='crc-bank.py version 0.0.1', options_first=True)

# Check account and cluster associations actually exist
# -> these won't exist for dump or repopulate
if not (arguments['dump'] or arguments['repopulate']):
    check_account_and_cluster(arguments['<account>'])

# Connect to the database and get the limits table
# Absolute path ////
db = dataset.connect('sqlite:///{0}'.format(DATABASE))
table = db['crc']

# For each insert/update/check, do operations
if arguments['insert']:
    # Check if database item already exists
    check_insert_item_in_table(table, arguments['<account>'])

    # Check <su_limit_hrs>
    service_units = check_service_units(arguments['<su_limit_hrs>']) 

    # Insert the limit
    table.insert(dict(account=arguments['<account>'], su_limit_hrs=service_units,
                 date=date.today(), percent_informed=False, limit_informed=False))

    # Log the action
    log_action("Account: {0} Insert: {1}".format(arguments['<account>'], service_units))

elif arguments['modify']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'modify')

    # Check <su_limit_hrs>
    service_units = check_service_units(arguments['<su_limit_hrs>']) 

    # Modify the limit
    table.update(dict(account=arguments['<account>'], su_limit_hrs=service_units,
                 date=date.today(), percent_informed=False, limit_informed=False), ['account'])

    # Log the action
    log_action("Account: {0} Modify: {1}".format(arguments['<account>'], service_units))

elif arguments['add']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'modify')

    # Check <su_limit_hrs>
    service_units = check_service_units(arguments['<su_limit_hrs>']) 
    service_units += table.find_one(account=arguments['<account>'])['su_limit_hrs']

    # Modify the limit, but not the date
    table.update(dict(account=arguments['<account>'], su_limit_hrs=service_units,
                 percent_informed=False, limit_informed=False), ['account'])

    # Log the action
    log_action("Account: {0} Add, New Limit: {1}".format(arguments['<account>'], service_units))

elif arguments['check_service_units_limit']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'check')

    # Get the usage from `sshare` for the account on each cluster
    command = "sshare --noheader --account={0} --cluster={1} --format=RawUsage"
    raw_usage = 0
    for cluster in CLUSTERS:
        raw_usage += int(popen(command.format(arguments['<account>'],
                               cluster)).read().split('\n')[1].strip())

    # raw usage is in CPU Seconds
    raw_usage /= (60 * 60)

    # Get limit in database
    limit = table.find_one(account=arguments['<account>'])['su_limit_hrs']

    # Check for 90% usage, send email
    if limit == 0 or limit == -1:
        percent = 0
    else:
        percent = 100 * int(raw_usage) / limit

    # If the limit is -1 the usage is unlimited
    if limit != -1 and int(raw_usage) > limit:
        # Account reached limit, set hold on account
        command = "sacctmgr -i modify account where account={0} cluster={1} set GrpTresRunMins=cpu=0"
        for cluster in CLUSTERS:
            popen(command.format(arguments['<account>'], cluster))

        if limit != 0:
            informed = table.find_one(account=arguments['<account>'])['limit_informed']
            if not informed:
                email_text = '''To Whom it May Concern,

                Your allocation on MODIFY has run out of SUs. The one-year allocation started on {0}.

                Thanks,

                The Proposal Bot
                '''

                # Send PI an email
                From = "proposal_bot@MODIFY"
                command = "sacctmgr -n list account account={0} format=description"
                username = popen(command.format(arguments['<account>'])).read().strip()
                To = "{0}@MODIFY".format(username)

                begin_date = table.find_one(account=arguments['<account>'])['date']

                email = MIMEText(email_text.format(begin_date))

                email["Subject"] = "Your allocation on MODIFY"
                email["From"] = From
                email["To"] = To

                # Send the message via our own SMTP server, but don't include the
                # envelope header.
                s = smtplib.SMTP('localhost')
                s.sendmail(From, [To], email.as_string())
                s.quit()

                # Log the action
                log_action("Account: {0} Held".format(arguments['<account>']))

                # PI has been informed
                table.update(dict(account=arguments['<account>'], limit_informed=True),
                            ['account'])

    elif limit != -1 and percent >= 90:
        informed = table.find_one(account=arguments['<account>'])['percent_informed']
        if not informed:
            # Account is close to limit, inform PI
            email_text = '''To Whom it May Concern,

            Your allocation on MODIFY is at {0}% usage. The one-year allocation started on {1}.

            Thanks,

            The Proposal Bot
            '''

            # Send PI an email
            From = "proposal_bot@MODIFY"
            command = "sacctmgr -n list account account={0} format=description"
            username = popen(command.format(arguments['<account>'])).read().strip()
            To = "{0}@MODIFY".format(username)

            begin_date = table.find_one(account=arguments['<account>'])['date']

            email = MIMEText(email_text.format(percent, begin_date))

            email["Subject"] = "Your allocation on MODIFY"
            email["From"] = From
            email["To"] = To

            # Send the message via our own SMTP server, but don't include the
            # envelope header.
            s = smtplib.SMTP('localhost')
            s.sendmail(From, [To], email.as_string())
            s.quit()

            # PI has been informed
            table.update(dict(account=arguments['<account>'], percent_informed=True),
                        ['account'])

elif arguments['reset_usage']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'reset_usage')

    # Reset sshare usage
    command = "sacctmgr -i modify account where account={0} cluster={1} set RawUsage=0"
    for cluster in CLUSTERS:
        popen(command.format(arguments['<account>'], cluster))

    # Update the date in the database
    table.update(dict(account=arguments['<account>'], date=date.today(), percent_informed=False, limit_informed=False), ['account'])

    # Log the action
    log_action("Account: {0} Reset".format(arguments['<account>']))

elif arguments['check_end_of_date_limit']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'check')

    # Check date is 366 or more days from previous
    db_date = table.find_one(account=arguments['<account>'])['date']
    current_date = date.today()
    comparison_days = current_date - db_date

    if comparison_days.days > 365:
        # If the usage was unlimited, just update the date otherwise set to 10K
        limit = table.find_one(account=arguments['<account>'])['su_limit_hrs']
        if limit == -1 or limit == 0:
            table.update(dict(account=arguments['<account>'], date=date.today(), percent_informed=False, limit_informed=False),
                        ['account'])

            # Log the action
            log_action("Account: {0} End of Date Update".format(arguments['<account>']))
        else:
            table.update(dict(account=arguments['<account>'], su_limit_hrs=10000,
                        date=date.today(), percent_informed=False, limit_informed=False), ['account'])
            log_action("Account: {0} End of Date Reset".format(arguments['<account>']))

        # Reset raw usage
        command = "sacctmgr -i modify account where account={0} cluster={1} set RawUsage=0"
        for cluster in CLUSTERS:
            popen(command.format(arguments['<account>'], cluster))

elif arguments['get_sus']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'check')

    # Print out SUs
    string = "Account {0} on MODIFY has {1} SUs"
    sus = table.find_one(account=arguments['<account>'])['su_limit_hrs']
    print(string.format(arguments['<account>'], sus))

elif arguments['release_hold']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'check')

    # Get the usage from `sshare` for the account and cluster
    command = "sshare --noheader --account={0} --cluster={1} --format=RawUsage"
    raw_usage = 0
    for cluster in CLUSTERS:
        raw_usage += int(popen(command.format(arguments['<account>'], cluster)).read().split('\n')[1].strip())

    # raw usage is in CPU Seconds
    raw_usage /= (60 * 60)

    # Get limit in database
    limit = table.find_one(account=arguments['<account>'])['su_limit_hrs']
    
    # Make sure raw usage is less than limit
    if int(raw_usage) < limit:
        # Account reached limit, remove hold on account
        command = "sacctmgr -i modify account where account={0} cluster={1} set GrpTresRunMins=cpu=-1"
        for cluster in CLUSTERS:
            popen(command.format(arguments['<account>'], cluster))

        # Log the action
        log_action("Account: {0} Released Hold".format(arguments['<account>']))
    else:
        exit("ERROR: The raw usage on the account is larger than the limit... you'll need to add SUs")

elif arguments['three_month_check']:
    # Check if database item exists
    check_item_in_table(table, arguments['<account>'], 'check')

    # Get today's date and end_date from table
    today = date.today()
    begin_date = table.find_one(account=arguments['<account>'])['date']

    # End date is the begin_date + 365 days
    end_date = begin_date + timedelta(365)
    delta = end_date - today
    
    # Make sure limit isn't 0 or -1
    limit = table.find_one(account=arguments['<account>'])['su_limit_hrs']

    # If the dates are separated by 90 days and the limits aren't 0 or -1 send an email
    if delta.days == 90 and limit != -1:
        email_text = '''To Whom it May Concern,

        Your proposal on cluster MODIFY will reset and 10K SUs will be added to your account on {0}.

        Thanks,

        The Proposal Bot
        '''

        # Send PI an email
        From = "MODIFY"
        command = "sacctmgr -n list account account={0} format=description"
        username = popen(command.format(arguments['<account>'])).read().strip()
        To = "{0}@MODIFY".format(username)
        email = MIMEText(email_text.format(end_date))

        email["Subject"] = "Your allocation on MODIFY"
        email["From"] = From
        email["To"] = To

        # Send the message via our own SMTP server, but don't include the
        # envelope header.
        s = smtplib.SMTP('localhost')
        s.sendmail(From, [To], email.as_string())
        s.quit()

elif arguments['dump']:        
    if not exists(arguments['<filename>']):
        items = db['crc'].all()
        dataset.freeze(items, format='json', filename=arguments['<filename>'])
    else:
        exit("ERROR: file {0} exists, don't want you to overwrite a backup".format(arguments['<filename>']))

elif arguments['repopulate']:
    if exists(arguments['<filename>']):
        print("DANGER: This function OVERWRITES crc-bank.db, are you sure you want to do this? [y/N]")
        choice = raw_input().lower()
        if choice == "yes" or choice == "y":
            # Get the contents
            contents = json.load(open(arguments['<filename>']))
            
            # Drop the current table and recreate it
            table.drop()
            table = db['crc']
            
            # Fix the contents['results'] list of dicts
            for item in contents['results']:
                # Python 2.6 doesn't support a read from string for dates
                str_to_int = [int(x) for x in item['date'].split('-')]
                item['date'] = date(str_to_int[0], str_to_int[1], str_to_int[2])
                item['su_limit_hrs'] = int(item['su_limit_hrs'])

            # Insert the list                
            table.insert_many(contents['results'])
    else:
        exit("ERROR: file {0} doesn't exist? Can't repopulate from nothing".format(arguments['<filename>']))
