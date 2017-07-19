#!/usr/bin/env bash

home_dir=/absolute/path/to/scripts
crc_bank=$home_dir/crc-bank.py
cron_logs=$home_dir/logs/cron.log

# generate a list of all of the accounts
accounts=($(sacctmgr list accounts -n format=account%30))

for i in ${accounts[@]}; do
    if [ $i != "root" ]; then
        $crc_bank check_service_units_limit $i >> $cron_logs 2>&1
        $crc_bank check_end_of_date_limit $i >> $cron_logs 2>&1
        $crc_bank three_month_check $i >> $cron_logs 2>&1
    fi
done
