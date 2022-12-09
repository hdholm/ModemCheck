#!/usr/bin/env python3
#
# ModemCheck.py - A simple script to monitor a Netgear CM1150V Cable Modem.
#                 It may or may not work for other Netgear Cable Modems.
#
# Copyright (c) 2020 Howard Holm
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import argparse
import getpass
import json
import logging
import re
import requests
import sys
from datetime import timedelta
from pytimeparse.timeparse import timeparse
from requests.auth import HTTPBasicAuth
from time import gmtime, mktime, sleep, strftime, strptime

version = '1.0'

prev_run = 0       # Global - retain data between runs to avoid disk read
prev_boot = 0      # Global - retain data between runs to avoid disk read
prev_uptime = 0    # Global - retain data between runs to avoid disk read
running_data = {}  # Global - retain data between runs to avoid disk read
logger = logging.getLogger(__name__)


def ISO_time(epochtime):
    """  Essentially shorthand for datetime.isoformat() without having to
         import datetime or deal with the vagaries of datetime objects
         when they're otherwise unneeded.
    """
    return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(epochtime))


def fetch_stats(password, user='admin', datafile_name='modem_stats.json'):
    """ Function to call the modem and compare statistics to its current set.
        We can't just parse the HTML because for some unfathamable reason
        the data we need is in string arrays in the JavaScript functions.
     """

    global prev_run  # holds the previous run version of freqs
    global prev_boot
    global prev_uptime
    global running_data

    # A dictionary of dictionaries indexed by channel number of current
    # downstream channel data in form {'status':, 'modulation':, 'channel ID':,
    # 'Frequency':, 'Power':, 'SNR':, 'Correctable Err':, 'Uncorrectable Err':}
    channels = {}

    # A dictionary of dictionaries indexed by frequecy of current downstream
    # data in form {'Channel ID':, 'Power':, 'SNR':, 'Correctable Err':,
    # 'Uncorrectable Err':}
    freqs = {}

    # get the page of data (and JavaScript) from the modem
    while(1):
        try:
            # I usually wouldn't hard code URLs, but they're hard coded in the
            # modem, so why not. The while loop is because if the modem is
            # rebooting the script aborts unless we "keep trying" until page.ok
            page = requests.get('http://192.168.100.1/',
                                auth=HTTPBasicAuth(user, password))
            jar = page.cookies
            page = requests.get('http://192.168.100.1/DocsisStatus.htm',
                                cookies=jar,
                                auth=HTTPBasicAuth(user, password))
        except Exception:
            logger.error('Error(s) trying to access modem URL')
            sleep(30)
        if page.ok:
            break

    # scrape the page.content for the "interesting" downstream channel data
    downstream = re.search(
        b'InitDsTableTagValue.*var tagValueList = \'32[|]' +
        b'(.*)\';.*function InitCmIpProvModeTag', page.content, re.DOTALL)
    if downstream is not None:
        downstream_data = downstream.group(1).split(b'|')
        downstream_data.pop()  # remove extraneous end field
        while downstream_data:
            channel_num = int(downstream_data.pop(0))
            channels[channel_num] = {}
            channels[channel_num][
                'Status'] = downstream_data.pop(0).decode('utf-8')
            channels[channel_num][
                'Modulation'] = downstream_data.pop(0).decode('utf-8')
            channels[channel_num][
                'Channel ID'] = int(downstream_data.pop(0))
            channels[channel_num][
                'Frequency'] = downstream_data.pop(0).decode('utf-8')
            channels[channel_num][
                'Power'] = float(downstream_data.pop(0).decode('utf-8'))
            channels[channel_num][
                'SNR'] = float(downstream_data.pop(0))
            channels[channel_num][
                'Correctable Err'] = int(downstream_data.pop(0))
            channels[channel_num][
                'Uncorrectable Err'] = int(downstream_data.pop(0))
        logger.debug(f'Channels dict: {channels}')
    else:
        logger.error(
            f'Web page contained bogus data: {page.content}')
        raise ValueError('Web page contained bogus status data.')

    # scrape the page.content for the current modem uptime
    boot_data = re.search(
        b'InitTagValue.*var tagValueList = \'(.*)\';.*function InitUpdateView',
        page.content, re.DOTALL)
    if boot_data is not None:
        boot_list = boot_data.group(1).split(b'|')
        # Convert the "Current System Time" to seconds since epoch
        sys_time = int(mktime(strptime((boot_list[10].decode('utf-8')))))
        # Convert the "Uptime" to seconds since epoch
        uptime = timeparse(boot_list[14].decode('utf-8'))
        boot_time = sys_time - uptime
        logger.debug(f'SysTime::{ISO_time(sys_time)}  ' +
                     f'Uptime::{timedelta(seconds=uptime)}')
    else:
        logger.error(f'Web page contained bogus data: {page.content}')
        raise ValueError('Web page contained bogus time data.')

    # Create a frequency vs. channel number based structure
    # We won't need to save everything we have for the channel
    # and we'll do some checks while we walk the channels
    for chan_idx in channels:
        chan_dict = channels[chan_idx]
        chan_freq = chan_dict['Frequency']
        freqs[chan_freq] = {}
        freqs[chan_freq]['Channel ID'] = chan_dict['Channel ID']
        freqs[chan_freq]['Power'] = chan_dict['Power']
        freqs[chan_freq]['SNR'] = chan_dict['SNR']
        freqs[chan_freq]['Correctable Err'] = chan_dict['Correctable Err']
        freqs[chan_freq]['Uncorrectable Err'] = chan_dict['Uncorrectable Err']
        # Check if SNR outside range
        if chan_dict['SNR'] < 36.0:
            logger.warning(f'{ISO_time(sys_time)}: Channel {chan_freq} ' +
                           f'SNR too low: {chan_dict["SNR"]}')
        # Check if Power outside range
        if abs(chan_dict['Power']) > 7.0:
            logger.warning(f'{ISO_time(sys_time)}: Channel {chan_freq} ' +
                           f' Power too high: {chan_dict["Power"]}')
    logger.debug(f'Frequency dict: {freqs}')

    # prev_run is defined from the previous globals run then use it for
    # efficiency  otherwise, pull it from the data file, if no data file
    # then must be new installation
    if not prev_run:
        try:
            # Check to see if we have saved stats stored on disk
            with open(datafile_name) as f:
                (prev_run, running_data, prev_boot, prev_uptime) = json.load(f)
                logger.debug(f'Recovered Prev_run dict: {prev_run}')
                logger.debug(f'Recovered Running dict: {running_data}')
                logger.debug(f'Recovered Previous Boot: {prev_boot}')
                logger.debug(f'Recovered Previous Uptime: {prev_uptime}')
        except IOError:
            # Assume the file doesn't exist
            # initialize prev_run so the compares don't traceback
            prev_run = freqs
            prev_boot = boot_time
            prev_uptime = uptime
            logger.debug(
                'No existing prev_run. Setting prev_run to current data.')

    # Sometimes on critical modem errors boot_time moves back a few seconds
    # and there seems to be a few second "jitter" in the uptime.
    if boot_time > prev_boot + 60:
        # Error rates must have been reset to zero by a reboot,
        # so baseline every frequency as zero
        prev_run = freqs
        for channel in prev_run:
            prev_run[channel]['Correctable Err'] = 0
            prev_run[channel]['UnCorrectable Err'] = 0
        logger.info(f'Modem Rebooted at {ISO_time(boot_time)} ' +
                    f'Currently up {timedelta(seconds=uptime)}')
        logger.info(f'Previous boot at {ISO_time(prev_boot)} ' +
                    f'Last up {timedelta(seconds=prev_uptime)}')

    # see if we have any new errors to report/keep track of
    # If the modem sees enough critial errors it will reset without
    # "rebooting" so uptime looks good, even though all the counters
    # have reset.  This is hard to detect, but we do our best.
    new_data = {}
    for chan_freq in prev_run:
        if chan_freq in list(freqs.keys()):
            new_correctable = freqs[chan_freq][
                'Correctable Err'] - prev_run[chan_freq]['Correctable Err']
            new_uncorrectable = freqs[chan_freq][
                'Uncorrectable Err'] - prev_run[chan_freq]['Uncorrectable Err']
            # if any channel goes bad, reset them all and break out
            if new_correctable < 0 or new_uncorrectable < 0:
                logger.info(f'Channel: {chan_freq} Negative errors'
                            ' - resetting previous counters')
                for old_freq in prev_run:
                    prev_run[old_freq]['Correctable Err'] = 0
                    prev_run[old_freq]['Uncorrectable Err'] = 0
                break

    for chan_freq in prev_run:
        if chan_freq in list(freqs.keys()):
            new_correctable = freqs[chan_freq][
                'Correctable Err'] - prev_run[chan_freq]['Correctable Err']
            new_uncorrectable = freqs[chan_freq][
                'Uncorrectable Err'] - prev_run[chan_freq]['Uncorrectable Err']
            if (new_correctable or new_uncorrectable):
                new_data[chan_freq] = (new_correctable, new_uncorrectable)
        else:
            new_data[chan_freq] = (0, 0)
            logger.info(f'Channel: {chan_freq} no longer utiltized')
            logger.debug(f'Channel: {chan_freq} Freqs keys: ' +
                         f'{list(freqs.keys())}')

    for chan_freq in freqs:
        # Check for new frequencies (not in previous run) that have errors
        if chan_freq not in list(prev_run.keys()):
            new_correctable = freqs[chan_freq]['Correctable Err']
            new_uncorrectable = freqs[chan_freq]['Uncorrectable Err']
            if (new_correctable or new_uncorrectable):
                new_data[chan_freq] = (new_correctable, new_uncorrectable)

    if new_data:
        running_data[sys_time] = new_data
        logger.info(f'New errors at {ISO_time(sys_time)}: {new_data}')
    logger.debug(f'Running data now: {running_data}')

    prev_run = freqs
    prev_boot = boot_time
    prev_uptime = uptime
    with open(datafile_name, 'w') as f:
        json.dump((prev_run, running_data, boot_time, uptime), f)
    logger.debug(f'Data refreshed Boot Time ({boot_time}) ' +
                 f'{ISO_time(boot_time)}')
    logger.debug(f'Data refreshed Uptime ' +
                 f'({uptime}) {timedelta(seconds=uptime)}')
    logger.info(f'Data refreshed System Time ({sys_time}) ' +
                f'{ISO_time(sys_time)}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=('A script to monitor the signal quality of a Netgear'
                     'CM1050V cable modem'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--quiet', action='store_true',
                        default=None, help='display only critical errors')
    parser.add_argument('-v', '--verbose', action='count', default=None,
                        help='optional multiple increases in logging')
    parser.add_argument('-V', '--version', action='version',
                        version=f'{parser.prog} {version}')
    parser.add_argument('-l', '--log',
                        help='optional log file (will be appended)')
    parser.add_argument('-d', '--datafile', help='file name of data store',
                        default='ModemData.json')
    parser.add_argument('-p', '--passfile',
                        help='specify file to read modem password from')
    args = parser.parse_args()

    # set up log destination and verbosity from the command line
    logger.setLevel(logging.DEBUG)
    # create formatter
    stamped_formatter = logging.Formatter(
        '%(asctime)s::%(levelname)s::%(name)s::%(message)s')
    unstamped_formatter = logging.Formatter(
        '%(levelname)s:%(name)s:%(message)s')
    if args.log:
        # set up a log file and stderr
        fh = logging.FileHandler(args.log)
        fh.setFormatter(stamped_formatter)
        ch = logging.StreamHandler()
        ch.setFormatter(unstamped_formatter)
        if not args.quiet:
            ch.setLevel(logging.WARNING)
        else:
            ch.setLevel(logging.CRITICAL)
        logger.addHandler(ch)
    elif args.quiet and args.verbose:
        parser.error('Can not have both verbose and quiet unless using a log' +
                     ' file (in which case the quiet applies to the console.)')
    else:
        # file handler is stderr
        fh = logging.StreamHandler()
        fh.setFormatter(unstamped_formatter)
    if args.quiet:
        fh.setLevel(logging.CRITICAL)
    if args.verbose is None:
        # default of error
        fh.setLevel(logging.ERROR)
    elif args.verbose == 1:
        # level up one to info
        fh.setLevel(logging.WARNING)
    elif args.verbose == 2:
        # go for our current max of debug
        fh.setLevel(logging.INFO)
    elif args.verbose >= 3:
        # go for our current max of debug
        fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # Get the modem password
    if args.passfile:
        with open(args.passfile) as pf:
            modem_password = pf.readline().rstrip('\n')
    else:
        modem_password = getpass.getpass('Modem Password: ')
    logger.debug(f"Password argument set to {modem_password}")

    while (1):
        fetch_stats(password=modem_password, datafile_name=args.datafile)
        sleep(300)
