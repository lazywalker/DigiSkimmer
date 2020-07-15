# -*- coding: utf-8 -*-
#
# timespan - Check if timestamps fall within specific boundaries
# Copyright (c) 2012 Justine Alexandra Roberts Tunney
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
r"""

    timespan
    ~~~~~~~~

    Timespans allow you to check if a timestamp falls within a specified list
    of boundaries.  For example, you might want to program your phone system
    to only accept calls Mon-Fri from 9 a.m. to 5 p.m. except on holidays like
    Christmas.

    Timespans are specified in the form of ``times|daysofweek|days|months``.
    If your timespan starts with ``!`` it'll match timestamps falling outside
    the specified range.

    Determine if timestamp is during 9 a.m. to 5 p.m. Monday through Friday
    business hours::

        >>> from datetime import datetime
        >>> dt = datetime(2012, 3, 29, 12, 0)  # Thursday @ Noon
        >>> match('9:00-17:00|mon-fri|*|*', dt)
        True
        >>> match('9:00-17:00|mon-fri', dt)
        True
        >>> match('9:00-17:00', dt)
        True

    Determine if within business hours, excluding Christmas::

        >>> dt = datetime(2012, 12, 25, 12, 0)  # X-Mas Tuesday @ Noon
        >>> match('9:00-17:00|mon-fri|*|*', dt)
        True
        >>> match(['9:00-17:00|mon-fri|*|*', '!*|*|25|dec'], dt)
        False
        >>> dt = datetime(2012, 12, 24, 12, 0)  # X-Mas Eve Monday @ Noon
        >>> match(['9:00-17:00|mon-fri|*|*', '!*|*|25|dec'], dt)
        True

    Determine if within any of several timespans::

        >>> dt = datetime(2012, 3, 29, 12, 0)  # Thursday @ Noon
        >>> match(['9:00-11:00|mon-fri|*|*', '13:00-17:00|mon-fri|*|*'], dt, match_any=True)
        False
        >>> match(['9:00-13:00|mon-fri|*|*', '14:00-17:00|mon-fri|*|*'], dt, match_any=True)
        True
        >>> match(['9:00-10:00|mon-fri|*|*', '11:00-17:00|mon-fri|*|*'], dt, match_any=True)
        True

    Multiple timespans can be a list or newline delimited::

        >>> dt = datetime(2012, 12, 25, 12, 0)  # X-Mas Tuesday @ Noon
        >>> match('9:00-17:00|mon-fri|*|*\n!*|*|25|dec', dt)
        False

    More examples::

        >>> thetime = datetime(2002, 12, 25, 22, 35)  # X-Mas on Wednesday
        >>> match('09:00-18:00|mon-fri|*|*', thetime)
        False
        >>> match('09:00-16:00|sat-sat|*|*', thetime)
        False
        >>> match('*|*|1|jan', thetime)
        False
        >>> match('*|*|25|dec', thetime)
        True
        >>> match('23:00-02:00|wed|30-25|dec-jan', thetime)
        False
        >>> match('22:00-02:00|wed|30-25|dec-jan', thetime)
        True
        >>> thetime = datetime(2006, 9, 21, 12, 30)
        >>> match('09:00-18:00|mon-fri|*|*', thetime)
        True
        >>> match('09:00-16:00|sat-sat|*|*', thetime)
        False
        >>> match('*|*|1-1|jan-jan', thetime)
        False
        >>> match('*|*|25-25|dec-dec', thetime)
        False
        >>> match('23:00-02:00|wed|30-25|dec-jan', thetime)
        False

        >>> birth = datetime(1984, 12, 18, 6, 30) # tuesday
        >>> dows = ['mon', 'tue', 'wed', 'fri', 'sat', 'sun']
        >>> [match('*|%s|*|*' % (s), birth) for s in dows]
        [False, True, False, False, False, False]
        >>> [match('*|%s-%s|*|*' % (s, s), birth) for s in dows]
        [False, True, False, False, False, False]
        >>> match('*|mon-wed|*|*', birth)
        True
        >>> match('*|mon-wed|*|*', birth)
        True
        >>> match('*|wed-mon|*|*', birth)
        False

        >>> bizhr = [
        ...     '9:00-17:00|mon-fri|*|*',
        ...     '!*|*|1|jan',
        ...     '!*|*|25|dec',
        ...     '!*|thu|22-28|nov',
        ... ]
        >>> match(bizhr, datetime(2012, 12, 24, 12, 00))
        True
        >>> match(bizhr, datetime(2012, 12, 24, 8, 00))
        False
        >>> match(bizhr, datetime(2012, 12, 24, 20, 00))
        False
        >>> match(bizhr, datetime(2012, 12, 25, 12, 00))
        False
        >>> match(bizhr, datetime(2013, 1, 1, 12, 00))
        False

    The BNF syntax for timespans is as follows::

        x ::= [0-9] | [0-9] x

        time  ::= x ':' x
        times ::= '*' | time | time '-' time

        dow ::= 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'
        dows ::= '*' | dow | dow '-' dow

        days ::= '*' | x | x '-' x

        month ::= 'jan' | 'feb' | 'mar' | 'apr' | 'may' | 'jun' | 'jul'
                | 'aug' | 'sep' | 'oct' | 'nov' | 'dec'
        months ::= '*' | month | month '-' month

        timespan ::= times
                   | times '|' dows
                   | times '|' dows '|' days
                   | times '|' dows '|' days '|' months

        timespan2 ::= timespan
                    | '!' timespan

        timespans ::= timespan2
                    | timespan2 '\n' timespans

"""

import sys
from datetime import datetime, time


__version__ = '0.1'
WEEKDAYS = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6}
MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5,
          'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10,
          'nov': 11, 'dec': 12}


def match(timespans, dt=None, match_any=False):
    """Determine if timestamp falls within one or more timespans"""
    dt = dt or datetime.now()
    strtype = str if sys.version_info[0] >= 3 else basestring
    if isinstance(timespans, strtype):
        timespans = timespans.splitlines()
    timespans = [ts for ts in timespans if ts.strip()]
    if match_any:
        return any(match_one(timespan, dt) for timespan in timespans)
    else:
        return all(match_one(timespan, dt) for timespan in timespans)


def match_one(timespan, dt=None):
    """Matches against only a single timespan"""
    timespan = timespan.strip()
    dt = dt or datetime.now()
    if timespan.startswith('!'):
        inverse = True
        timespan = timespan[1:]
    else:
        inverse = False
    ts = timespan.split('|') + ['*', '*', '*']
    times, dows, days, months = ts[:4]
    if times != '*':
        lo, hi = _span(times, _parse_time)
        if not _inside(dt.time(), lo, hi):
            return inverse
    if dows != '*':
        lo, hi = _span(dows, _parse_weekday)
        if not _inside(dt.weekday(), lo, hi):
            return inverse
    if days != '*':
        lo, hi = _span(days, int)
        if not _inside(dt.day, lo, hi):
            return inverse
    if months != '*':
        lo, hi = _span(months, _parse_month)
        if not _inside(dt.month, lo, hi):
            return inverse
    return not inverse


def _span(val, f):
    vals = [f(s) for s in val.split('-')]
    if len(vals) == 1:
        return vals[0], vals[0]
    else:
        lo, hi = vals
        return lo, hi


def _inside(x, lo, hi):
    if hi == time(0):
        return lo <= x
    elif hi >= lo:
        return lo <= x <= hi
    else:
        return x >= lo or x <= hi


def _parse_time(s):
    return datetime.strptime(s, '%H:%M').time()


def _parse_weekday(s):
    if s in WEEKDAYS:
        return WEEKDAYS[s[:3].lower()]
    else:
        raise ValueError('bad weekday', s)


def _parse_month(s):
    if s in MONTHS:
        return MONTHS[s[:3].lower()]
    else:
        raise ValueError('bad month', s)


if __name__ == "__main__":
    import doctest
    doctest.testmod()