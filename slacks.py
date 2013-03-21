#!/usr/bin/env python2.7
"""
"slacks" is the third revision of the "pants" hours leaderboard for the Brown
CS consulting program. This revision is intended to work with the Workday hours
system.

Specifically, because there is no (known) Workday API, it parses the files that
the csched command uses to create the weekly schedule (sched, sched.meta, and
/sched.week.[0-9]+/). The sched file format uses the following format:

    a1 login

where a is the shift, 1 is the day of the week, starting at Monday == 1, and
login is the login of the consultant who's shift the timeslot is. The shifts
are on hourly intervals (so a == 9am, b == 10am, etc.). This pattern breaks in
a bad way on the TR 1.5 hour shifts where a == 9am, b == 10:30am, and
d == 12pm. This accounts for some icky coding and constants.

Sub files are of the format:

    1) a1 login
    2) a1 FREE_SHIFT_LOGIN requester

where 1) is equivalent to the standard format, as is the a1 variable of 2).
requester is the login of the consultant requesting the sub.

By the way, pacifists are boring! Go start a pants war! Edit pants.json today!

Written in Spring 2013 by Michael Comella (mcomella).

Previous revisions:
* (Fall 2012) trousers: Nathan Malkin (nmalkin)
* (?) pants: ?

"""
CONSULT_DIR = '/admin/consult/'
SCHED_DIR = CONSULT_DIR + 'data/sched/'
PERM_SCHED_FILE = SCHED_DIR + 'sched'
SCHED_FILE_PREFIX = SCHED_DIR + 'sched.week.'
META_FILE = SCHED_DIR + 'sched.meta' # csched metadata.
OPTIONS_FILE = CONSULT_DIR + 'bin/slacks/pants.json'
AUX_HOUR_FILE = CONSULT_DIR + 'bin/slacks/aux_hours.json'

AUX_HOUR_PREFIX = 'aux hours: ' # Prefix for args help string.
AUX_HOUR_NOT_LOGGED = AUX_HOUR_PREFIX + 'No hours logged for the current ' + \
        'week. Cannot delete.'

START_WEEK_OFFSET = 0 # The index of the initial consulting week.
START_DAY_OFFSET = 1 # (is Monday) To zero-index dates in PERM_SCHED_FILE.
MON, TUES, WED, THURS, FRI, SAT, SUN = range(0, 7)

SHIFT_START_HOUR = 9 # 9am
SHIFT_END_HOUR = 28 # 4am (during reading period)
SHIFT_RANGE = SHIFT_END_HOUR - SHIFT_START_HOUR

LB_HDR_FMT = ' {:>5}  {:>3}  {}' # Leaderboard header format to string.format().
LB_HOUR_FMT = ' {:>5.2f}  {:>3}  {}' # Leaderboard hours listing.

FREE_SHIFT_LOGIN = 'FREE'

ERR_LOGTAG = 'depantsed! -'

from copy import deepcopy
from datetime import datetime
from getpass import getuser
from operator import itemgetter
from random import randint
from time import mktime
import argparse
import json
import fcntl, os, sys

def main():
    args = set_and_parse_args()
    metadata = get_metadata()
    options = get_options()

    perm_sched = CSched(PERM_SCHED_FILE)
    cur_week_num = metadata['cur_week']
    cur_week_file = SCHED_FILE_PREFIX + str(cur_week_num)
    cur_week_sched = perm_sched.get_copy_with_subs(cur_week_file)
    cur_week_hours = cur_week_sched.get_hours_sum()

    mode = 'r+' if args.add or args.delete else 'r'
    with open(AUX_HOUR_FILE, mode) as f:
        fcntl.lockf(f, fcntl.LOCK_EX) # Acquire exclusive file lock.
        aux_hours = json.load(f)

        if not args.add and not args.delete and not args.list:
            print_hours(args, options, cur_week_hours)
        elif args.add: add_aux_hours(args, cur_week_num, aux_hours, f)
        elif args.delete: delete_aux_hours(cur_week_num, aux_hours, f)
        if args.list: print_aux_hours()

        fcntl.lockf(f, fcntl.LOCK_UN) # Unlock.

def set_and_parse_args():
    """Sets up, parses and returns any command line arguments.

    The arguments are returned as the object returned from the
    argparse.ArgumentParser.parse_args() method.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--monikers', help='replace consultant logins '
            'with monikers', action='store_true')
    # TODO: -w: specify a week (+/-int, int, & all)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--add', nargs=2, metavar=('MIN', 'COMMENT'),
            action='store', help=AUX_HOUR_PREFIX + 'add MIN minutes with '
            'COMMENT')
    group.add_argument('-d', '--delete', action='store_true',
            help=AUX_HOUR_PREFIX + 'deletes the most recent hours block')
    parser.add_argument('-l', '--list', action='store_true',
            help=AUX_HOUR_PREFIX + 'display logged hours')

    namespace = parser.parse_args()
    if namespace.add: # Verify --add MIN is an int.
        try: int(namespace.add[0])
        except ValueError: parser.error('argument -a/--add: expected int MIN')
    return namespace

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
        if len(file_lines) != 1:
            exit('get_metadata', 'Unknown format in "' + META_FILE + '".')
        # string.split(sep=whitespace, maxsplit=3).
        start_date, num_weeks, extend_start, sched_header = tuple(
                file_lines[0].split(None, 3))
        md = {
            'num_weeks': int(num_weeks),
            'extend_start': int(extend_start),
            'sched_header': sched_header.rstrip()
        }
        md['start_date'] = datetime.strptime(start_date, '%m/%d/%Y')

        # NOTE: This requires the date listed in META_FILE to be on the same
        # day of the week as START_DAY_OFFSET.
        date_delta = datetime.now() - md['start_date']
        md['cur_week'] = date_delta.days / 7 + START_WEEK_OFFSET
        return md

def get_options():
    """Returns options json object from OPTIONS_FILE.

    Typically the options should include monikers and champion messages.

    """
    with open(OPTIONS_FILE) as f:
        return json.load(f)

class CSched:
    """Represents a given week's schedule and associated utility methods.

    The schedule is represented in CSched._sched_arr as a list of list where
    the outer list represents the day of the week and the inner list represents
    the which consultant is on duty (by login) at the given time by half hour
    increments. The time of the 0th index is determined by the constant
    SHIFT_START_HOUR. For example, with SHIFT_START_HOUR = 9,

                M          T      etc.
    9:00am  [mcomella] [akenyon]
    9:30am  [mcomella] [akenyon]
    10:00am [nmalkin]  [mcomella]
    etc.

    CSched._sched_arr[1][0] = 'akenyon'

    Shifts in an unknown state are listed as None (the initial value; thus no
    input file has overidden this value yet) while any subbed shifts are
    equivalent to the constant FREE_SHIFT_LOGIN.

    """
    def __init__(self, file_path=None):
        self._sched_arr = [[None] * SHIFT_RANGE * 2 for i in range(7)] # Zero.
        if file_path: self.update_shifts_from_file(file_path)

    def update_shifts_from_file(self, path):
        """Updates the shifts in the CSched object with the file at path."""
        with open(path) as f:
            for line in f:
                tokens = [t.strip().lower() for t in line.split()]
                if len(tokens) == 0 or tokens[0][0] == '#': continue # Comment.
                shift, login = tokens[:2]
                # tokens[2] is the sub requester, which is irrelevant.
                half_hour_index = (ord(shift[0]) - ord('a')) * 2
                day_index = int(shift[1]) - START_DAY_OFFSET

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
        """Copies the CSched, updating it with matched shifts from the path."""
        sub_sched = deepcopy(self)
        sub_sched.update_shifts_from_file(sub_file_path)
        return sub_sched

    def get_hours_sum(self):
        """Returns the sum of logged hours for each consultant in the CSched.

        Output is returned as a dict of {'login': (hours, num_shifts)}.

        """
        hsum = {}
        num_shifts = {}
        prev_shift_login = None # To find consecutive shifts.
        now = datetime.now()
        now_day_index, now_hhour_index = \
                self.convert_datetime_to_shift_index(now)
        remaining_minutes = now.minute if now.minute < 30 else now.minute - 30
        for day_index, day in enumerate(self._sched_arr):
            if day_index > now_day_index: break # Future.
            today = True if day_index == now_day_index else False
            for hhour_index, shift_login in enumerate(day):
                if today and (hhour_index > now_hhour_index): break # Future.
                if shift_login is not None:
                    if today and (hhour_index == now_hhour_index):
                        # Add minutes passed during the current shift.
                        hsum[shift_login] = hsum.get(shift_login, 0) + \
                                remaining_minutes / 60.
                        num_shifts[shift_login] = \
                                num_shifts.get(shift_login, 0)
                        break
                    hsum[shift_login] = hsum.get(shift_login, 0) + 0.5
                    if prev_shift_login != shift_login: # Not consecutive.
                        num_shifts[shift_login] = \
                                num_shifts.get(shift_login, 0) + 1
                prev_shift_login = shift_login

        # Merge the hsum & num_shifts dicts.
        return dict((login, (hours, num_shifts.get(login, None)) ) for
                (login, hours) in hsum.iteritems())

    def convert_datetime_to_shift_index(self, datetime):
        """Converts the given datetime object to self._sched_arr indicies."""
        day_index = datetime.weekday()
        hhour_offset = 0 if datetime.minute < 30 else 1 # 30 minute blocks.
        hhour_index = (datetime.hour - SHIFT_START_HOUR) * 2 + hhour_offset

        # Workaround for hours post-midnight which take on hours > 24 (ex: 1am
        # is hour 25 - NOT INDEX) and thus are considered to be the same day as
        # the previous day.
        if datetime.hour < SHIFT_START_HOUR:
            day_index -= 1
            hhour_index += 24 * 2
        return (day_index, hhour_index)

def print_hours(args, options, hdict):
    """Prints the hours in the {'login': (hours, num_shifts)} dict."""
    monikers = displaying_monikers(args)

    print # Blank.
    print LB_HDR_FMT.format('Hours', 'Num', 'Who')
    print LB_HDR_FMT.format('-----', '---', '---')
    hours_list = sorted(hdict.iteritems(), key=itemgetter(1), reverse=True)
    for login, shift_data in hours_list:
        hours, num_shifts = shift_data
        if login.upper() == FREE_SHIFT_LOGIN: continue
        if monikers and login in options['monikers']:
            login = options['monikers'][login]
        print LB_HOUR_FMT.format(hours, num_shifts, login)
    print # Blank.

    # Print champion message corresponding to the winning consultant.
    if displaying_monikers(args) and len(hours_list) > 0:
        winner, hours = hours_list[0]
        if winner in options['champion_messages']:
            print options['champion_messages'][winner]
            print # Blank.

        if winner == getuser():
            # TODO: Make the winner message more clever. From pants.json?
            print 'You are the winner, ' + winner + '!'
            num_experts = str(randint(0, 11))
            print num_experts + ' out of 10 experts agree: You might want ' + \
                    'to leave the Sunlab from time to time.'

def displaying_monikers(args):
    """Returns True if the output should display monkers, False otherwise."""
    cmd_name = os.path.basename(__file__)
    return args.monikers or cmd_name == 'pants'

def add_aux_hours(args, cur_week_num, aux_hours, f):
    """Adds the hours given in args to aux_hours, writing it to open file f."""
    cur_week_num = str(cur_week_num)
    if cur_week_num not in aux_hours: aux_hours[cur_week_num] = {}
    cur_week_hours = aux_hours[cur_week_num]
    login = getuser()
    if login not in cur_week_hours: cur_week_hours[login] = []

    minutes, comment = int(args.add[0]), args.add[1]
    shift_info = (int(mktime(datetime.utcnow().timetuple())), minutes, comment)
    cur_week_hours[login].append(shift_info)
    replace_aux_hours(aux_hours, f)

    print AUX_HOUR_PREFIX + 'Added ' + str(minutes) + ' minutes with ' + \
            'comment, "' + comment + '".'

def print_aux_hours():
    print 'NOT YET IMPLEMENTED: print_aux_hours()'

def delete_aux_hours(cur_week_num, aux_hours, f):
    """Removes logged aux_hours for the current user, writing to open file f.

    This removal pops the most recently added shift, like a stack. A shift is
    only removeable if it was logged during the current week.

    """
    cur_week_num = str(cur_week_num)
    login = getuser()
    if cur_week_num in aux_hours and login in aux_hours[cur_week_num] and \
            len(aux_hours[cur_week_num][login]) > 0:
        users_cur_week_shifts = aux_hours[cur_week_num][login]
        removed_shift = users_cur_week_shifts.pop()
        replace_aux_hours(aux_hours, f)
        print AUX_HOUR_PREFIX + 'Removed ' + str(removed_shift[1]) + ' ' + \
                'minute shift with comment, "' + removed_shift[2] + '".'
    else:
        print AUX_HOUR_NOT_LOGGED

def replace_aux_hours(aux_hours, f):
    """Replaces the contents of open file f with the aux_hours JSON object."""
    f.truncate(0)
    f.seek(0)
    json.dump(aux_hours, f, indent=2)
    f.write('\n') # To make vim happy. ^_^

def exit(func_name, message):
    sys.exit(ERR_LOGTAG + ' ' + func_name + '(): ' + message)

if __name__ == '__main__':
    main()
