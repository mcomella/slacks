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
START_DAY = 1 # is Monday.
MON, TUES, WED, THURS, FRI, SAT, SUN = range(START_DAY, START_DAY + 7)

SHIFT_START_HOUR = 9 # 9am
SHIFT_END_HOUR = 28 # 4am (during reading period)
SHIFT_RANGE = SHIFT_END_HOUR - SHIFT_START_HOUR

LB_HDR_FMT = ' {:>5}  {}' # Leaderboard header format to string.format().
LB_HOUR_FMT = ' {:>5.2f}  {}' # Leaderboard hours list.

ERR_LOGTAG = 'depantsed! -'

from copy import deepcopy
from datetime import datetime
from operator import itemgetter
import argparse
import sys

def main():
    args = set_and_parse_args()
    metadata = get_metadata()
    perm_sched = CSched(PERM_SCHED_FILE)

    cur_week_file = SCHED_DIR + 'sched.week.' + str(metadata['cur_week'])
    cur_week_sched = perm_sched.get_copy_with_subs(cur_week_file)
    cur_week_hours = cur_week_sched.get_hours_sum()
    print_hours(cur_week_hours)

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

class CSched:
    # TODO: Doc. [day][hour]

    def __init__(self, file_path=None):
        # TODO: Doc.
        self._sched_arr = [[None] * SHIFT_RANGE * 2 for i in range(7)] # Zero.
        if file_path: self.update_from_file(file_path)

    def update_from_file(self, path):
        # TODO: Doc.
        # TODO: Keep num shifts.
        with open(path) as f:
            for line in f:
                tokens = line.split(); map(lambda s: s.strip().lower(), tokens)
                shift, login = tokens[:2]
                # tokens[2] is the sub requester, which is irrelevant.
                half_hour_index = (ord(shift[0]) - ord('a')) * 2
                day_index = int(shift[1]) - START_DAY

                if day_index in (TUES, THURS) and half_hour_index in (0, 8):
                    # 1.5 hour shifts starting on the hour.
                    offa, offb = (0, 3)
                elif day_index in (TUES, THURS) and half_hour_index in (2, 10):
                    # 1.5 hour shifts starting on the half hour.
                    offa, offb = (1, 4)
                else: # 1 hour shift starting on the hour.
                    offa, offb = (0, 2)
                hhour_bounds = (half_hour_index + offa, half_hour_index + offb)
                for hhour in range(*hhour_bounds):
                    self._sched_arr[day_index][hhour] = login

    def get_copy_with_subs(self, sub_file_path):
        # TODO: Doc.
        sub_sched = deepcopy(self)
        sub_sched.update_from_file(sub_file_path)
        return sub_sched

    def get_hours_sum(self):
        # TODO: Doc.
        hsum = {}
        for day in self._sched_arr:
            for shift_login in day:
                if shift_login is not None:
                    hsum[shift_login] = hsum.get(shift_login, 0) + 0.5
        return hsum

def print_hours(hdict):
    # TODO: Doc.
    print # Blank.
    print LB_HDR_FMT.format('Hours', 'Who')
    print LB_HDR_FMT.format('-----', '---')
    hours_list = sorted(hdict.iteritems(), key=itemgetter(1), reverse=True)
    for login, hours in hours_list:
        print LB_HOUR_FMT.format(hours, login)
    print # Blank.
    # TODO: Print champion message.
    # TODO: Print message to champion.

def exit(func_name, message):
    sys.exit(ERR_LOGTAG + ' ' + func_name + '(): ' + message)

if __name__ == '__main__':
    main()
