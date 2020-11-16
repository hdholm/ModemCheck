#!/usr/bin/env python
""" ModemDisplay.py A simple script to pull data from the
    ModemCheck data file and publish a scatter plot graph
"""
import argparse
import json
import logging
import plotly.express as px
from time import gmtime, strftime

logger = logging.getLogger(__name__)


def ISO_time(epochtime):
    """  Essentially shorthand for datetime.isoformat() without having to
         import datetime or deal with the vagaries of datetime objects
         when they're otherwise unneeded.
    """

    return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(epochtime))


def display_stats(datafile_name, outfile_name):
    """ Read the modem stats from datafile and produce an HTML chart
    """

    logger.debug(f'In display_stats: '
                 f'datafile_name={datafile_name} '
                 f'outfile_name={outfile_name}')
    running_data = {}
    X = []  # X axis array for display
    Y = []  # Y axis array for display
    C = []  # Color array for display contains error type at X,Y
    S = []  # Size array for display contains number of errors at X,Y

    # Get saved stats stored on disk
    with open(datafile_name) as f:
        (prev_run, running_data, prev_boot, prev_uptime) = json.load(f)
        logger.debug(f'Recovered Prev_run dict: {prev_run}')
        logger.debug(f'Recovered Running dict: {running_data}')
        logger.debug(f'Recovered Previous Boot: {prev_boot}')
        logger.debug(f'Recovered Previous Uptime: {prev_uptime}')
    for event_time, data_points in running_data.items():
        for freq in sorted(list(data_points.keys())):
            if data_points[freq][0]:
                X.append(ISO_time(int(event_time)))
                Y.append(int(freq.rstrip(' Hz')))
                C.append('Correctable')
                S.append(data_points[freq][0])
            if data_points[freq][1]:
                X.append(ISO_time(int(event_time)))
                Y.append(int(freq.rstrip(' Hz')))
                C.append('Uncorrectable')
                S.append(data_points[freq][1])

    fig = px.scatter(x=X, y=Y, color=C, size=S,
                     labels={'x': 'Date/Time (in UTC)',
                             'y': 'Frequency (in Hz)',
                             'color': 'Type of Error',
                             'size': 'Number of Corrupted Packets',
                             }, title="CM1150V Packet Errors")
    fig.update_layout(legend=dict(orientation="h",
                                  yanchor="bottom",
                                  y=1.02,
                                  xanchor="right",
                                  x=1
                                  ), xaxis_type='date')

    if outfile_name is None:
        fig.show()
    else:
        fig.write_html(outfile_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="What this script does",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--quiet', action='store_true',
                        default=None, help='display only critical errors')
    parser.add_argument('-v', '--verbose', action='count', default=None,
                        help='optional multiple increases in logging')
    parser.add_argument('-V', '--version', action='version',
                        version=f'{parser.prog} 1.0')
    parser.add_argument('-l', '--log',
                        help='optional log file (will be appended)')
    parser.add_argument('-d', '--datafile', help='file name of data store',
                        default='ModemData.json')
    parser.add_argument('-o', '--outfile', nargs="*",
                        help='output file for HTML display')
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

    if args.outfile and len(args.outfile) > 1:
        parser.error('Only one output file is allowed.')
    if args.outfile == []:
        # Use a default file
        display_stats(args.datafile, 'ModemDisplay.html')
    else:
        display_stats(args.datafile, args.outfile[0])
