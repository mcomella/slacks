#!/usr/bin/env python2.7
"""
"slacks" is the third revision of the "pants" hours leaderboard for the Brown
CS consulting program. This revision is intended to work with the Workday hours
system.

Specifically, because there is no (known) Workday API, it parses the files that
the csched command uses to create the weekly schedule (sched.perm and
/sched.week.[0-9]+/).

Pacifists are boring! Go start a pants war! Edit pants.json today!

Written in Spring 2013 by Michael Comella (mcomella).
"""

CONSULT_DIR = '/admin/consult/'
SCHED_DIR = CONSULT_DIR + 'data/sched/'

META_FILE = SCHED_DIR + 'sched.meta' # Metadata file associated with csched.
START_WEEK = 0 # The index of the initial consulting week.

ERR_LOGTAG = 'depantsed! -'

from datetime import datetime
import argparse
import sys

def main():
    args = set_and_parse_args()
    metadata = get_metadata()

def set_and_parse_args():
    """Sets up, parses and returns any command line arguments.

    The arguments are returned as the object returned from the
    argparse.ArgumentParser.parse_args() method.

    """
    parser = argparse.ArgumentParser()
    # TODO: -m: with monikers
    # TODO: -w: specify a week (+/-int, int, & all)
    return parser.parse_args()

def get_metadata():
    """Retrieves metadata associated with csched.

    The metadata is read from the file at the path specified by META_FILE which
    has the expected format:

    MM/DD/YYYY num_weeks extend_start sched_header
    where MM/DD/YYYY   = (str) the start date of the semester
          num_weeks    = (int) the number of weeks in the semester
          extend_start = (int) the number weeks before extended hours (reading
                         period) begins
          sched_header = (str) the text displayed at the top of the schedule

    Returns an instance of the Metadata class with these values.

    """
    with open(META_FILE) as f:
        file_lines = f.readlines()
        if len(file_lines) is not 1:
            exit('Unknown format in "' + META_FILE + '".')
        # string.split(sep=whitespace, maxsplit=3).
        return Metadata(*tuple(file_lines[0].split(None, 3)))

class Metadata:
    """A module for miscellaneous csched metadata."""
    # TODO: Implement __str__.
    # TODO: Implement __repr__.

    def __init__(self, start_date, num_weeks, extend_start, sched_header):
        """Creates an instance of the Metadata class.

        Arguments should be passed as found in the META_FILE (see
        get_metadata()).

        """
        self.num_weeks = int(num_weeks)
        self.extend_start = int(extend_start)
        self.sched_header = sched_header.rstrip()

        # TODO: Handle dates specified with leading zeroes.
        # Convert date from string to datetime instance.
        date_list = [int(x) for x in start_date.split('/')]
        if len(date_list) is not 3:
            exit('Unknown date format in "' + META_FILE + '".')
        self.start_date = datetime(date_list[2], date_list[0],
                date_list[1]) # YMD.

        date_delta = datetime.now() - self.start_date
        self.cur_week = date_delta.days / 7 + START_WEEK

def exit(message): sys.exit(ERR_LOGTAG + message)

if __name__ == '__main__':
    main()
