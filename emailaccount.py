#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import email.header
import os
import re
import sys

from utils import writeLog, human_readable, toU

PY3 = sys.version_info[0] >= 3
if PY3:
    def fromUtf(s):
        return s
    def toUtf(s):
        return s
    def unicode(s):
        return s
else:
    def fromUtf(s):
        return s.decode("utf8", "replace")
    def toUtf(s):
        return s.encode("utf8", "replace")


class emailAccount(object):
    """Base class for an email account. Use connect() and
    disconnect() accordingly. Use getMboxes() to get a list
    of mailboxes in this account."""
    def __init__(self, name):
        self._name = name
        self.boxes = []
        self.acctType = None
    @property
    def name(self):
        return self._name
    def __str__(self):
        return self._name
    def connect(self):
        """Connect to account, throw exception on failure"""
        pass
    def disconnect(self):
        """Disconnect."""
        pass
    def getMboxes(self):
        """Obtain list of mailboxes on this account. This may
        involve network activity."""
        return []
    def mboxes(self):
        """Return the list of mailboxes previously obtained
        by getMboxes()."""
        return self.boxes


class mailbox(object):
    """This object represents one mailbox on a server, or one folder
    on the local system."""
    # Return values from checkForUpdates
    NO_UPDATES = 0      # No change since last asked
    BOX_APPENDED = 1    # Email has been added to the end
    BOX_CHANGED = 2     # Mailbox changed and should be re-read
    # Status values for status and getOverview callback
    STATE_EMPTY = 0         # no information loaded yet
    STATE_READING = 1       # load in progress
    STATE_FINISHED = 2      # load or save complete
    STATE_INTERRUPTED = 3   # interrupted by user
    STATE_LOCKED = 4        # unable to acquire lock
    STATE_SAVING = 5        # writing back

    def __init__(self, name, path):
        self._name = name
        self.path = path
        self._state = mailbox.STATE_EMPTY
        self.messages = None
        self.msgdict = None
        self.nUnread = None
        self.nNew = None
    @property
    def name(self):
        return self._name
    def isTrash(self):
        return self._name == "Trash"
    @property
    def state(self):
        return self._state
    def active(self):
        return True
    def __str__(self):
        return self._name
    def __repr__(self):
        return "<mailbox %s>" % self._name
    def nmessages(self):
        """Return # of messages in this mailbox, or None if not known."""
        return 0 if self.messages == None else len(self.messages)
    def summaries(self):
        """Return array of message summaries."""
        return self.messages
    def getOverview(self, callback):
        """Get all of the Subject, From, To, and Date headers.
        Return the total # of messages.
        As this could conceivably take a lot of time, an optional
        callback(mailbox, count, percent, status, msg) is called once per second,
        and at the conclusion."""
        self.state = mailbox.STATE_FINISHED
        return mailbox.STATE_FINISHED
    def save(self, callback):
        """Save the mailbox. For some types of mailbox (e.g. mbox),
        this can be very very slow. The optional
        callback(mailbox, count, percent, status, msg) is called
        once per second and at the conclusion."""
        self.state = mailbox.STATE_FINISHED
        return mailbox.STATE_FINISHED
    def checkForUpdates(self):
        """Return NO_UPDATES, BOX_APPENDED, or BOX_CHANGED."""
        return NO_UPDATES
    def getAllHeaders(self):
        """Return array of dicts of selected headers from all messages."""
        return []
    def getHeaders(self, n):
        """Return full headers from this message. Indexing starts at 0.
        May return None for a non-available message."""
        return None
    def getMessage(self, n):
        """Return full message as an email.message object.
        May return None for a non-available message."""
        return None
    def nextMessage(self, n):
        """Return index of next message after this, or None."""
        return None if not self.messages or n >= len(self.messages)-1 else n+1
    def previousMessage(self, n):
        """Return index of previous message before this, or None."""
        return None if not self.messages or n <= 0 else n-1
    def nextUnread(self, n):
        """Return index of next unread message after this, or None."""
        if not self.messages: return None
        for i in range(n+1, len(self.messages)):
            if not self.messages[i].status & messageSummary.FLAG_READ:
                return i
        return None
    def previousUnread(self, n):
        """Return index of previous unread message before this, or None."""
        if not self.messages: return None
        for i in range(n-1, -1, -1):
            if not self.messages[i].status & messageSummary.FLAG_READ:
                return i
        return None

    # Special mailboxes and their sort order
    specials = { 'inbox':0, 'drafts':1, 'sent':2, 'sent messages':3,
        'junk':4, 'deleted messages':5, 'trash':6, 'archive':7,}

    def __lt__(self, other):
      """Sorting mailboxes is a little tricky. Certain mailboxes
      go right at the top, the remainder are sorted alphabetically."""
      sn = self._name.lower()
      on = other._name.lower()
      specials = self.specials
      if sn in specials and on in specials:
          return specials[sn] < specials[on]
      if sn in specials:
          return True
      if on in specials:
          return False
      return self._name < other._name
    def __eq__(self, other):
      return self._name == other._name

    @staticmethod
    def readHeaders(ifile):
        """Read headers until a blank line, "From ", or EOF reached.
        Leaves file pointer pointing at whatever ended the scan."""
        hdrs = {}
        key = None
        while True:
            offset = ifile.tell()
            line = ifile.readline()
            if not line:
                return hdrs
            line = line.rstrip()
            if not line or line.startswith("From "):
                ifile.seek(offset)
                return hdrs
            if line[0] in (' ','\t'):   # continuation
                if key:
                    hdrs[key] += u' ' + parseIso(line[1:])
            else:
                line = line.split(':',1)
                key = line[0]
                value = line[1].strip() if len(line) > 1 else u''
                hdrs[key] = parseIso(value)



class messageSummary(object):
    """Represents the summary data of a message."""
    subjwid = 30
    fromwid = 20
    datewid = 16        # yyyy-mm-dd hh:mm
    sizewid = 6
    width = 8 + subjwid + fromwid + datewid + sizewid
    sentbox = False
    FLAG_DELETED = 1
    FLAG_NEW = 2
    FLAG_READ = 4
    FLAG_ANSWERED = 8
    FLAG_FORWARDED = 0x10
    FLAG_DIRECT = 0x20
    FLAG_CC = 0x40
    FLAG_SELECTED = 0x80
    FLAG_FLAGGED = 0x100
    def __init__(self):
        self.offset = 0
        self.size = 0
        self.From = None
        self.To = None
        self.Subject = None
        self.Date = None
        self.status = 0
        self.MessageId = None
        self.uid = None
        self.key = None
        self.idx = None         # Counting from 0
    def __repr__(self):
        return "<MboxMessage \"%s\">" % self.Subject
    def getValues(self):
        # Fit the status into three letters
        status = self.status
        c1 = '*' if status & self.FLAG_FLAGGED else ' '
        c2 = 'D' if status & self.FLAG_DELETED else \
             'U' if not (status & self.FLAG_READ) else \
             'A' if status & self.FLAG_ANSWERED else \
             'F' if status & self.FLAG_FORWARDED else \
             'N' if status & self.FLAG_NEW else ' '
        c3 = '+' if status & self.FLAG_DIRECT else \
             '-' if status & self.FLAG_CC else ' '
        status = c1+c2+c3
        return (status, self.Subject, self.From, self.Date,
            human_readable(self.size))


if PY3:
    def parseIso(s):
        """Accept ascii text, parse per RFC 2047, return unicode."""
        if "=?" not in s: return s
        parts = email.header.decode_header(s)
        rval = []
        for part in parts:
            if part[1] is None:
                rval.append(part[0])
            else:
                try:
                    rval.append(part[0].decode(part[1]))
                except:
                    rval.append(u"???")
        return u''.join(rval).replace(u"\n",u"").replace(u"\r",u"")

else:
    iso_re = re.compile(r"""(=\?.+?\?.+?\?.+?\?=)""")
    def parseIso(s):
        """Bug in the python 2 parser, we'll need to split the
        string first."""
        # To be precise, the Python 2.7 decode_header() function fails
        # with "=?UTF-8?B?VFJFTkQgTE9BTiBDT01QQU5Z?=<notification@teemi.my>"
        if "=?" not in s: return toU(s)
        rval = []
        parts = iso_re.split(s)
        for part in parts:
            if part:
                parts2 = email.header.decode_header(part)
                for part2 in parts2:
                    if part2[1] is None:
                        rval.append(unicode(part2[0]))
                    else:
                        try:
                            rval.append(part2[0].decode(part2[1]))
                        except:
                            rval.append(u"???")
        return u''.join(rval).replace(u"\n",u"").replace(u"\r",u"")
