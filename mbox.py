#!/usr/bin/env python
# -*- coding: utf8 -*-

import email.parser
import os
import socket
import sys
import time

from emailaccount import *
import dotlock
import filerange
from utils import writeLog

if sys.platform.startswith('linux'):
    OS = 'Linux'
elif sys.platform.startswith('darwin'):
    OS = 'MacOS'
elif sys.platform.startswith('win'):
    OS = 'Windows'
elif sys.platform.startswith('freebsd'):
    OS = 'FreeBSD'
else:
    OS = 'Unknown'      # TODO: other operating systems as the need arises.

HOST = socket.gethostname()
dummyMsgID = 1233

def dummyMID():
    global dummyMsgID
    dummyMsgID += 1
    return "<%dGenerated@%s>" % (dummyMsgID, HOST)


class MboxAccount(emailAccount):
    def __init__(self, name, path, config):
        emailAccount.__init__(self, name)
        self.acctType = "local"
        self.inbox = path
        if config.has_option("mailrc","folder"):
            self.folder = config.get("mailrc","folder")
        else:
            self.folder = None
        writeLog("New Berkeley mbox email box %s, %s" % (name, path))

    def getMboxes(self):
        self.boxes = [Mbox("INBOX", self.inbox)]
        if self.folder:
            path = self.folder
            try:
                folders = os.listdir(path)
                folders = filter(self.exclude, folders)
                folders = filter(lambda x: os.path.isfile(os.path.join(path,x)),
                    folders)
                folders = [Mbox(x, os.path.join(path, x)) for x in folders]
                self.boxes.extend(folders)
                self.boxes.sort()
            except Exception as e:
                writeLog("Failed to read folder %s, %s" % (path, e))
        return self.boxes

    @staticmethod
    def exclude(name):
        """Patterns that are not legit mailbox folders."""
        return not name.startswith("dovecot") and \
                not name.startswith('.')


class Mbox(mailbox):
    """I had hoped to use mailbox.mbox here, but it just doesn't
    do everything I need. I don't think it was designed for
    some of the truly massive mboxes I have in mind."""
    def __init__(self, name, path):
        mailbox.__init__(self, name, path)
        self.size = os.path.getsize(path)
        self.parser = email.parser.Parser()
        self.busy = False               # Unavailable if True
        self.busy = name[1] is 'e'
        self.messages = []
        self.msgdict = {}
        self.nUnread = 0
        self.nNew = 0
    def __str__(self):
        return "%s (saving...)" % self.name if self.state == self.STATE_SAVING else self.name
    def active(self):
        # TODO: let main worry about this
        return self.state != self.STATE_SAVING
    def checkForUpdates(self):
        """Return True if the mailbox was updated by an external
        force since the last update."""
        # TODO
        return False
    def getAllHeaders(self):
        """Return array of selected headers from all messages."""
        # TODO
        return []
    def getHeaders(self, n):
        """Return full headers from this message. Indexing starts at 0.
        May return None for a non-available message."""
        if n < 0 or n >= len(self.messages):
            return None
        # TODO: confirm the mailbox hasn't changed
        msg = self.messages[n]
        ifile = open(self.path, "r")
        ifile = filerange.Filerange(ifile, msg.offset, msg.size)
        return self.parser.parse(ifile, True)
    def getMessage(self, n):
        """Return full text of this message as a dict divided into parts.
        May return None for a non-available message."""
        if n < 0 or n >= len(self.messages):
            return None
        # TODO: confirm the mailbox hasn't changed
        msg = self.messages[n]
        ifile = open(self.path, "r")
        ifile = filerange.Filerange(ifile, msg.offset, msg.size)
        return self.parser.parse(ifile)

    def getOverview(self, callback):
        """Get all of the Subject, From, To, and Date headers.
        Return the total # of messages.  As this could conceivably
        take a lot of time, an optional callback(mbox, count,
        isFinal, pct, message) is called every 0.5 seconds or so,
        and at the conclusion. If there are already mail summaries
        in self.messages, reading continues where it left off. If
        you want to start from scratch, set self.messages to None
        before calling this."""

        # TODO: run this in a background thread

        start = lastcb = lastrefresh = time.time()
        # Scan the mailbox, generating {to,from,subject,date,msgid,offset,size}
        # dicts and adding to self.messages
        # Every ten messages, check the time.
        # Every 0.5 seconds, send an update
        # Every 5 seconds, refresh the dotlock
        msgcount = len(self.messages)    # Only check every 100 messages
        if self.messages:
            lastOffset = self.messages[-1].offset
            offset = lastOffset + self.messages[-1].size
        else:
            lastOffset = 0  # Offset of last seen "From " line.
            offset = 0      # file offset
            self.msgdict = {}
            self.nUnread = 0
            self.nNew = 0
        # Programming note: I originally did "with open(...) as ifile",
        # but it resulted in "'I/O operation on closed file' in  ignored"
        try:
            ifile = open(self.path, "r")
            flock = dotlock.FileLock(ifile)
            dlock = dotlock.DotLock(self.path)
            ifile.seek(offset)
            if not self.lockboxes(flock, dlock):
                if callback:
                    callback(self, msgcount, 0, mailbox.STATE_LOCKED,
                        "Failed to lock mailbox %, timed out" % self.path)
                return mailbox.STATE_LOCKED

            while True:
                try:
                    (msg, offset) = self.getMessageSummary(ifile)
                    if not msg:
                        break
                    # We prefer X-UID as the dictionary key, else we'll use
                    # the message id.
                    msg.idx = msgcount
                    key = msg.key
                    self.messages.append(msg)
                    self.msgdict[key] = msg
                    msgcount += 1
                    if msg.status & messageSummary.FLAG_NEW: self.nNew += 1
                    if not (msg.status & messageSummary.FLAG_READ): self.nUnread += 1
                    if msgcount % 10 == 0:
                        now = time.time()
                        if now > lastcb + 0.5:
                            lastcb = now
                            if callback:
                                callback(self, msgcount, 100.*offset/self.size,
                                    mailbox.STATE_READING, None)
                            if now > lastrefresh + 5.0:
                                lastrefresh = now
                                dlock.refresh()
                except KeyboardInterrupt:
                    if callback:
                        callback(self, msgcount, 100.*offset/self.size,
                            mailbox.STATE_INTERRUPTED, "Interrupted by user")
                        return mailbox.STATE_INTERRUPTED

        finally:
            self.unlockboxes(flock, dlock)
            ifile.close()

        if callback:
            callback(self, msgcount,100., mailbox.STATE_FINISHED, None)
        return mailbox.STATE_FINISHED

    def getMessageSummary(self, ifile):
        """Scan for a "From " line, return its key headers."""
        # scan to "From " line, it *ought* to be the first one, but no
        # promises.
        while True:
            offset0 = ifile.tell()
            line = ifile.readline()
            if not line: return (None, None)
            if line.startswith("From "): break
        fullhdrs = self.readHeaders(ifile)
        offset = self.flushMessage(ifile)
        msg = messageSummary()
        msg.offset = offset0
        msg.size = offset - offset0
        if "From" in fullhdrs: msg.From = fullhdrs["From"]
        if "To" in fullhdrs: msg.To = fullhdrs["To"]
        if "Subject" in fullhdrs: msg.Subject = fullhdrs["Subject"]
        if "Date" in fullhdrs: msg.Date = fullhdrs["Date"]
        if "Status" in fullhdrs:
            status = fullhdrs["Status"]
            if 'R' in status: msg.status |= messageSummary.FLAG_READ
            if 'O' not in status: msg.status |= messageSummary.FLAG_NEW
        if "X-Status" in fullhdrs:
            status = fullhdrs["X-Status"]
            if 'A' in status: msg.status |= messageSummary.FLAG_ANSWERED
            if 'F' in status: msg.status |= messageSummary.FLAG_FLAGGED
            if 'D' in status: msg.status |= messageSummary.FLAG_DELETED
        if "X-UID" in fullhdrs: msg.uid = fullhdrs["X-UID"]
        if "Message-Id" in fullhdrs: msg.MessageId = fullhdrs["Message-Id"]
        elif "Message-ID" in fullhdrs: msg.MessageId = fullhdrs["Message-ID"]
        if msg.uid: msg.key = msg.uid
        elif msg.MessageId: msg.key = msg.MessageId
        else: msg.key = dummyMID()
        return (msg, offset)

    @staticmethod
    def flushMessage(ifile):
        """Read and discard input until find "From " line. Return file offset"""
        while True:
            offset = ifile.tell()
            line = ifile.readline()
            if not line:
                return offset
            if line.startswith("From "):
                ifile.seek(offset)
                return offset


    def lockboxes(self, filelock, dotlock):
        """Acquire both locks. Return False on failure."""
        if not filelock.lock(30):
            return False
        if not dotlock.lock(30):
            filelock.unlock()
            return False
        return True

    def unlockboxes(self, filelock, dotlock):
        dotlock.unlock()
        filelock.unlock()


