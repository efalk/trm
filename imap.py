#!/usr/bin/python
# -*- coding: utf8 -*-


import sys
import os
import getopt
import string
import signal
import socket
import time
import imaplib
import email.parser
import getpass
import re
import types
import fnmatch
import ast

import emailaccount
import screens
from utils import writeLog, configGet

PY3 = sys.version_info[0] >= 3
if PY3:
    basestring = str
    import configparser
else:
    import ConfigParser as configparser

# Numeric flag values. Most important flags have higher values
MBOX_MARKED = 0x1
MBOX_UNMARKED = 0x2
MBOX_NO_INFERIORS = 0x4
MBOX_CHILDREN = 0x8
MBOX_NO_CHILDREN = 0x10
MBOX_NO_SELECT = 0x20
MBOX_FLAGGED = 0x100
MBOX_TRASH = 0x200
MBOX_JUNK = 0x400
MBOX_SENT = 0x1000
MBOX_DRAFTS = 0x2000
MBOX_ARCHIVE = 0x4000
MBOX_ALL = 0x8000

verbose = 1
quiet = False
host = None
port = None
ssltls = None
authtype = None
user = None
passwd = None
timeout = None
longform = False
waitTime = 0.0
mailDir = None
notreally = False
prefix = ''
deleteFirst = False
force = False
includes = []
excludes = []

class imapException(Exception):
    pass

class imapAuthFailed(imapException):
    pass

class imapAccount(emailaccount.emailAccount):
    def __init__(self, name, section, config):
        emailaccount.emailAccount.__init__(self, name)
        self.acctType = "imap"
        #writeLog("section %s, options: %s" % (section, config.options(section)))
        self.host = configGet(config, section, "imap")
        self.port = configGet(config, section, "imapport")
        self.conn = configGet(config, section, "imapconn")
        self.user = configGet(config, section, "imapuser")
        self.passwd = configGet(config, section, "imappass")
        self.authtype = "plain"
        self.subbedOnly = True
        writeLog("host=%s, port=%s, conn=%s, user=%s, passwd=%s" %
            (self.host, self.port, self.conn, self.user, self.passwd))

    def needsPasswd(self):
        return self.passwd == None

    def setPasswd(self, pw):
        self.passwd = pw

    def connect(self):
      '''Connect to server, throw exception on failure.'''
      global verbose, timeout
      host = self.host
      port = self.port
      ssltls = self.conn == 'tls'
      if timeout:
        socket.setdefaulttimeout(timeout)
      if port == None and not ssltls:
        port = 143
      if port == None:
        port = 993 if ssltls else 143
      if verbose:
        writeLog('Connect to %s:%d, ssl %s' % (host, port, ssltls))
      try:
        if ssltls:
          self.srvr = imaplib.IMAP4_SSL(host, port)
        else:
          self.srvr = imaplib.IMAP4(host, port)
      except socket.error as e:
        raise imapException('failed to connect to %s, %s' % (host, e))
      try:
        self.srvLogin()
      except Exception as e:
        self.disconnect()
        raise
      return True

    def srvLogin(self):
      '''Execute login. Throw imapException on failure.'''
      global verbose

      srvr = self.srvr
      user = self.user
      passwd = self.passwd
      authtype = self.authtype

      if not authtype:
        for cap in srvr.capabilities:
          if cap.startswith('AUTH='):
            authtype = cap.split('=')[1].lower()
            break
      writeLog('Login user ' + user)
      try:
        if not authtype or authtype == 'plain':
          srvr.login(user, passwd)
          return True
        elif authtype == 'md5':
          srvr.login_cram_md5(user, passwd)
          return True
        else:
          raise imapException("Authtype %s not known" % authtype)
      except imaplib.IMAP4.error as e:
        writeLog("failure: %s" % str(type(e)))
        raise imapAuthFailed("Login failed: %s" % e)

    def disconnect(self):
        writeLog('Logout user ' + self.user)
        self.srvr.logout()

    def getMboxes(self):
        '''Return list of mailbox objects for this server.'''
        srvr = self.srvr
        mailboxes = srvr.list()
        if mailboxes[0] == 'OK':
            mailboxes = map(parseList, mailboxes[1])
            if self.subbedOnly:
                subbed = srvr.lsub()
                if subbed[0] == 'OK':
                    subbed = map(parseList, subbed[1])
                    subbed = set([x[2] for x in subbed])
                    subbed.add('INBOX')
                    writeLog("subbed: %s" % subbed)
                    mailboxes = filter(lambda x: x[2] in subbed, mailboxes)
            mailboxes = map(Mbox, mailboxes)
            mailboxes = filter(lambda x: not(x.flags & MBOX_NO_SELECT), mailboxes)
            mailboxes.sort()
            return mailboxes
        else:
            return None


class Mbox(emailaccount.mailbox):
    def __init__(self):
        self.flags = 0
        self.flaglist = []
        self.separator = ''
        self.name = ''

    def __init__(self, resp):
        '''Initialize a mailbox object from a LIST server response.'''
        writeLog("list response: %s" % resp)
        self.flaglist = resp[0]
        self.separator = resp[1]
        self.name = resp[2]
        self.flags = self.mboxFlags()

    def mboxFlags(self):
        flaglist = self.flaglist
        oflags = 0
        for flag in flaglist:
            flag = flag.lower()
            if flag in flagMap:
                oflags |= flagMap[flag]
        return oflags

    def FlagLetters(self):
        # Flags:
        #   * Marked
        flags = self.flags
        return '*' if flags & MBOX_MARKED else ' '


    def __str__(self):
        return self.FlagLetters() + self.name

    def __repr__(self):
        return '<imap.Mbox %s>' % self.name


# UTILITIES

flagMap = {'\\marked': MBOX_MARKED,
        '\\unmarked': MBOX_UNMARKED,
        '\\noinferiors': MBOX_NO_INFERIORS,
        '\\haschildren': MBOX_CHILDREN,
        '\\hasnochildren': MBOX_NO_CHILDREN,
        '\\all': MBOX_ALL,
        '\\archive': MBOX_ARCHIVE,
        '\\drafts': MBOX_DRAFTS,
        '\\junk': MBOX_JUNK,
        '\\sent': MBOX_SENT,
        '\\trash': MBOX_TRASH,
        '\\flagged': MBOX_FLAGGED,
        '\\noselect': MBOX_NO_SELECT,
      }


def parseList(srvresp):
  '''Scan string s for (lists) and strings. Return list of results'''
  rval = []
  s = srvresp.strip()
  while s:
    if s.startswith('('):
      i = s.find(')')
      if i < 1:
        print >>sys.stderr, "Malformed server response:", srvresp
        return None
      rval.append(s[1:i].split())
      s = s[i+1:].lstrip()
    elif s.startswith('"'):
      i = s.find('"',1)
      if i < 1:
        print >>sys.stderr, "Malformed server response:", srvresp
        return None
      rval.append(s[1:i])
      s = s[i+1:].lstrip()
    else:
      i = s.find(' ')
      if i < 0:
        i = len(s)
      rval.append(s[0:i])
      s = s[i:].lstrip()
  return rval

