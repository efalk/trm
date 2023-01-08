#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import sys

PY3 = sys.version_info[0] >= 3
if PY3:
    basestring = str
    import configparser
    # In Python3, curses takes unicode natively, so no
    # need to encode.
    def fromUtf(s):
        return s
    def toUtf(s):
        return s
    def unicode(s):
        return s
else:
    import ConfigParser as configparser
    def fromUtf(s):
        return s.decode("utf8", "replace")
    def toUtf(s):
        return s.encode("utf8", "replace")


loggingEnabled = True   # TODO: false
logfile = None
def writeLog(s):
    global logfile, loggingEnabled
    if not loggingEnabled:
        return
    if not logfile:
        logfile = open("logfile", "a")
    if not PY3 and type(s) == unicode:
        s = toUTF(s)
    print(s, file=logfile)
    logfile.flush()

def configGet(config, section, option, dflt=None):
    """Utility: read option or return default."""
    try:
        return config.get(section, option)
    except configparser.NoOptionError as e:
        return dflt

def configSet(config, section, option, value):
    """Utility: write option, create section if needed."""
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, option, value)

def toUTF(s):
    """Convert unicode string to utf-8."""
    if not PY3:
        s = s.encode('utf-8')
    return s

def fromUTF(s):
    """Convert utf-8 string to unicode."""
    if not PY3:
        s = s.decode('utf-8')
    return s

def toU(s):
    """Try to convert this string to unicode. There's a lot of
    bullshit encodings out there in email land, and sometimes you
    just have to guess."""
    encodings = ["utf8", "GB2312", "HZ-GB-2312",
        "ISO-8859-5", "windows-1251",
        "ISO-8859-1", "windows-1252",
        "ISO-8859-7", "windows-1253",
        "ISO-8859-8", "windows-1255",]
    try:
        return unicode(s)
    except:
        for encoding in encodings:
            try:
                return s.decode(encoding)
            except:
                pass
    # Hopeless
    rval = [c if c in string.printable else ("\\%2.2x" % ord(c)) for c in s]
    return u''.join(rval)

def human_readable(num, divisor=1024):
  num = float(num)
  for unit in ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z'):
    if abs(num) < divisor*10:
      return "%3.0f%s" % (num, unit)
    num /= divisor
  return "%.1fY" % num

