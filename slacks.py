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
# TODO: Merge the above text with the README text.

CONSULT_DIR = '/admin/consult/'
SCHED_DIR = CONSULT_DIR + 'data/sched/'
PERM_SCHED_FILE = SCHED_DIR + 'sched.perm'

META_FILE = SCHED_DIR + 'sched.meta' # Metadata file associated with csched.
START_WEEK = 0 # The index of the initial consulting week.

SHIFT_START_HOUR = 9 # 9am
SHIFT_END_HOUR = 28 # 4am (during reading period)
SHIFT_RANGE = SHIFT_END_HOUR - SHIFT_START_HOUR

ERR_LOGTAG = 'depantsed! -'

from datetime import datetime
import argparse
import sys

def main():
    args = set_and_parse_args()
    metadata = get_metadata()
    perm_sched = get_perm_sched()

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
    where start_date = (str) the start date of the semester as MM/DD/YYYY
          num_weeks = (int) the number of weeks in the semester
          extend_start = (int) the number weeks before extended hours (reading
                         period) begins
          sched_header = (str) the text displayed at the top of the schedule

    Returns a dictionary of metadata: {
        'start_date': (datetime) See above
        'num_weeks': (int) See above
        'extend_start': (int) See above
        'sched_header': (str) See above
        'cur_week': (int) A value specifying the number of weeks since the
                        starting week
    }

    """
    with open(META_FILE) as f:
        file_lines = f.readlines()
        if len(file_lines) is not 1:
            exit('get_metadata', 'Unknown format in "' + META_FILE + '".')
        # string.split(sep=whitespace, maxsplit=3).
        start_date, num_weeks, extend_start, sched_header = tuple(
                file_lines[0].split(None, 3))
        md = {
            'num_weeks': int(num_weeks),
            'extend_start': int(extend_start),
            'sched_header': sched_header.rstrip()
        }

        # TODO: Handle dates specified with leading zeroes.
        date_list = [int(x) for x in start_date.split('/')]
        if len(date_list) is not 3:
            exit('get_metadata', 'Unknown date format in "' + META_FILE + '".')
        md['start_date'] = datetime(date_list[2], date_list[0],
                date_list[1]) # YMD.

        # TODO: Make sure this actually returns the correct week.
        date_delta = datetime.now() - md['start_date']
        md['cur_week'] = date_delta.days / 7 + START_WEEK
        return md

def get_perm_sched():
    # TODO: Add doc.
    sched_arr = [[None] * 7 for i in range(SHIFT_RANGE)] # Zero array.
    with open(PERM_SCHED_FILE) as f:
        for line in f:
            tokens = line.split()
            shift = tokens[0]
            login = tokens[1]
            # tokens[2], if it exists, is the sub requester, which can be
            # blissfully ignored.
            hour_index = ord(shift[0]) - ord('a')
            day_index = int(shift[1]) - 1 # 0 is Monday.
            sched_arr[hour_index][day_index] = login
    return sched_arr

def exit(func_name, message):
    sys.exit(ERR_LOGTAG + ' ' + func_name + '(): ' + message)

if __name__ == '__main__':
    main()
