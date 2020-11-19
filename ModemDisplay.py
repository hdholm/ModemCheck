#!/usr/bin/env python
#
# ModemDisplay.py - A simple script to monitor a Netgear CM1150V Cable Modem.
#                   It depends on ModemCheck.py to do most of the work before
#                   This is ever called.
#                   It may or may not work for other Netgear Cable Modems.
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
""" ModemDisplay A simple script to pull data from the
    ModemCheck data file and publish a scatter plot graph
"""
import argparse
import json
import logging
import math
import plotly.graph_objects as go
from time import gmtime, strftime

logger = logging.getLogger(__name__)


def ISO_time(epochtime):
    """  Essentially shorthand for datetime.isoformat() without having to
         import datetime or deal with the vagaries of datetime objects
         when they're otherwise unneeded.
    """

    return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(epochtime))


def display_stats(datafile_name, outfile_name=None):
    """ Read the modem stats from datafile and produce an HTML chart
    """

    logger.debug(f'In display_stats: '
                 f'datafile_name={datafile_name} '
                 f'outfile_name={outfile_name}')
    running_data = {}

    # Get saved stats stored on disk
    with open(datafile_name) as f:
        (prev_run, running_data, prev_boot, prev_uptime) = json.load(f)
        logger.debug(f'Recovered Prev_run dict: {prev_run}')
        logger.debug(f'Recovered Running dict: {running_data}')
        logger.debug(f'Recovered Previous Boot: {prev_boot}')
        logger.debug(f'Recovered Previous Uptime: {prev_uptime}')

    fig = go.Figure()

    max_size = 0
    for index, err_type in enumerate(['Correctable', 'Uncorrectable']):
        X = []  # X axis array for display
        Y = []  # Y axis array for display
        S = []  # size of data point arrary for dispplay
        T = []  # array of text descriptions of data points
        for event_time, data_points in running_data.items():
            for freq in sorted(list(data_points.keys())):
                if data_points[freq][index]:
                    X.append(ISO_time(int(event_time)))
                    Y.append(int(freq.rstrip(' Hz')))
                    S.append(math.sqrt(data_points[freq][index]))
                    T.append(
                        f'{data_points[freq][index]} {err_type} Errors')
        fig.add_trace(go.Scattergl(
            x=X, y=Y, name=err_type, text=T, marker_size=S))
        max_size = max(max_size, max(S))

    fig.update_traces(
        mode='markers',
        marker=dict(
            sizemode='area',
            sizeref=2.*max_size/(50**2),
            sizemin=3)
    )

    fig.update_layout(legend=dict(orientation="h",
                                  yanchor="bottom",
                                  y=1.02,
                                  xanchor="right",
                                  x=1
                                  ),
                      xaxis=dict(type='date', title='Date/Time (in UTC)'),
                      yaxis_title='Frequency (in Hz)',
                      title="CM1150V Packet Errors")
    if outfile_name is None:
        fig.show()
    else:
        fig.write_html(outfile_name, include_plotlyjs='directory')


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

    if args.outfile is None:
        display_stats(args.datafile)
    else:
        if len(args.outfile) > 1:
            parser.error('Only one output file is allowed.')
        if args.outfile == []:
            # Use a default file
            display_stats(args.datafile, 'ModemDisplay.html')
        else:
            display_stats(args.datafile, args.outfile[0])
