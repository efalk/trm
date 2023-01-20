#!/usr/bin/env python
# -*- coding: utf8 -*-

import email.parser
import os
import socket
import sys
import time

import emailaccount
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


class MboxAccount(emailaccount.emailAccount):
    def __init__(self, name, path, config):
        super(MboxAccount,self).__init__(name)
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


class Mbox(emailaccount.mailbox):
    """I had hoped to use mailbox.mbox here, but it just doesn't
    do everything I need. I don't think it was designed for
    some of the truly massive mboxes I have in mind."""
    def __init__(self, name, path):
        super(Mbox,self).__init__(name, path)
        self.size = os.path.getsize(path)
        self.parser = email.parser.Parser()
        self.busy = False               # Unavailable if True
        self.busy = name[1] is 'e'
        self._summaries = []
        self.msgdict = {}
        self.nUnread = 0
        self.nNew = 0
        self.lastModified = None
        self.lastFrom = None
    def __str__(self):
        return "%s (saving...)" % self.name if self._state == self.STATE_SAVING else self.name
    def active(self):
        # TODO: let main worry about this
        return self.state != self.STATE_SAVING
    def checkForUpdates(self):
        """Return NO_UPDATES, BOX_APPENDED, or BOX_CHANGED."""
        # The mailbox state is NO_UPDATES after it's been read
        # (even if interrupted) and the timestamp and size are
        # recorded. If modified, we check to see if it was a simple
        # append, or a complete change requiring a reload. State
        # reverts back to NO_UPDATES after a reload.
        if self.updates == self.BOX_CHANGED:
            return self.BOX_CHANGED
        stat = os.stat(self.path)
        if stat.st_mtime == self.lastModified and stat.st_size == self.size:
            return self.updates
        size = self.size
        self.lastModified = stat.st_mtime
        self.size = stat.st_size
        #writeLog("size %d:%d" % (size, stat.st_size))
        if stat.st_size < size:
            # If the mailbox shrank, someone deleted something from it, and
            # the whole thing is invalid now.
            #writeLog("  size shrank")
            self.updates = self.BOX_CHANGED
            return self.BOX_CHANGED
        # Examine the last "From " line. If changed, then the mailbox has
        # been modified and is now invalid. Else, someone just appended
        # new mail.
        try:
            #writeLog("  open file %s" % self.path)
            with open(self.path, "r") as ifile:
                #writeLog("  seek to %d" % self._summaries[-1].offset)
                ifile.seek(self._summaries[-1].offset)
                line = ifile.readline()
                #writeLog("  read line %s:%s" % (line.rstrip(), self.lastFrom.rstrip()))
                if line == self.lastFrom:
                    #writeLog("  appended")
                    self.updates = self.BOX_APPENDED
                    return self.BOX_APPENDED
                else:
                    #writeLog("  changed")
                    self.updates = self.BOX_CHANGED
                    return self.BOX_CHANGED
        except Exception as e:
            writeLog("  exception %s" % e)
            self.updates = self.BOX_CHANGED
            return self.BOX_CHANGED
    def getAllHeaders(self):
        """Return array of selected headers from all messages."""
        # TODO
        return []
    def getHeaders(self, n):
        """Return full headers from this message. Indexing starts at 0.
        May return None for a non-available message."""
        if n < 0 or n >= len(self._summaries):
            return None
        # TODO: confirm the mailbox hasn't changed
        msg = self._summaries[n]
        ifile = open(self.path, "r")
        ifile = filerange.Filerange(ifile, msg.offset, msg.size)
        return self.parser.parse(ifile, True)
    def getMessage(self, n):
        """Return full text of this message as a dict divided into parts.
        May return None for a non-available message."""
        if n < 0 or n >= len(self._summaries):
            return None
        # TODO: confirm the mailbox hasn't changed
        msg = self._summaries[n]
        return msg.getMessage(self)

    def getOverview(self, callback):
        """Get all of the Subject, From, To, and Date headers.
        Return the total # of messages.  As this could conceivably
        take a lot of time, an optional callback(mbox, count,
        isFinal, pct, message) is called every 0.5 seconds or so,
        and at the conclusion. If there are already mail summaries
        in self._summaries, reading continues where it left off. If
        you want to start from scratch, set self._summaries to None
        before calling this."""

        # TODO: run this in a background thread

        if self.updates == self.BOX_CHANGED:
            # Need to start fresh
            self._summaries = []

        start = lastcb = lastrefresh = time.time()
        # Scan the mailbox, generating {to,from,subject,date,msgid,offset,size}
        # dicts and adding to self._summaries
        # Every ten messages, check the time.
        # Every 0.5 seconds, send an update
        # Every 5 seconds, refresh the dotlock
        msgcount = len(self._summaries)    # Only check every 100 messages
        if self._summaries:
            lastOffset = self._summaries[-1].offset
            offset = lastOffset + self._summaries[-1].size
        else:
            lastOffset = 0  # Offset of last seen "From " line.
            offset = 0      # file offset
            self.msgdict = {}
            self.nUnread = 0
            self.nNew = 0
        # Programming note: I originally did "with open(...) as ifile",
        # but it resulted in "'I/O operation on closed file' in  ignored"
        flock = dlock = None
        try:
            stat = os.stat(self.path)
            self.lastModified = stat.st_mtime
            ifile = open(self.path, "r")
            flock = dotlock.FileLock(ifile)
            dlock = dotlock.DotLock(self.path)
            ifile.seek(offset)
            if not self.lockboxes(flock, dlock):
                if callback:
                    callback(self, msgcount, 0, self.STATE_LOCKED,
                        "Failed to lock mailbox %s, timed out" % self.path)
                self.updates = self.NO_UPDATES
                self._state = self.STATE_LOCKED
                return self.STATE_LOCKED

            while True:
                try:
                    (msg, offset) = self.getMessageSummary(ifile)
                    if not msg:
                        break
                    # We prefer X-UID as the dictionary key, else we'll use
                    # the message id.
                    msg.idx = msgcount
                    key = msg.key
                    self._summaries.append(msg)
                    self.msgdict[key] = msg
                    msgcount += 1
                    if msg.status & msg.FLAG_NEW: self.nNew += 1
                    if not (msg.status & msg.FLAG_READ): self.nUnread += 1
                    if msgcount % 10 == 0:
                        now = time.time()
                        if now > lastcb + 0.5:
                            lastcb = now
                            if callback:
                                callback(self, msgcount, 100.*offset/self.size,
                                    self.STATE_READING, None)
                            if now > lastrefresh + 5.0:
                                lastrefresh = now
                                dlock.refresh()
                except KeyboardInterrupt:
                    if callback:
                        callback(self, msgcount, 100.*offset/self.size,
                            self.STATE_INTERRUPTED, "Interrupted by user")
                        self.updates = self.NO_UPDATES
                        self._state = self.STATE_INTERRUPTED
                        return self.STATE_INTERRUPTED

        finally:
            self.unlockboxes(flock, dlock)
            ifile.close()

        if callback:
            callback(self, msgcount,100., self.STATE_FINISHED, None)
        self.updates = self.NO_UPDATES
        self._state = self.STATE_FINISHED
        return self.STATE_FINISHED

    def getMessageSummary(self, ifile):
        """Scan for a "From " line, return its key headers."""
        # scan to "From " line, it *ought* to be the first one, but no
        # promises.
        while True:
            offset0 = ifile.tell()
            line = ifile.readline()
            if not line: return (None, None)
            if line.startswith("From "):
                self.lastFrom = line
                break
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
            if 'R' in status: msg.status |= msg.FLAG_READ
            if 'O' not in status: msg.status |= msg.FLAG_NEW
        if "X-Status" in fullhdrs:
            status = fullhdrs["X-Status"]
            if 'A' in status: msg.status |= msg.FLAG_ANSWERED
            if 'F' in status: msg.status |= msg.FLAG_FLAGGED
            if 'D' in status: msg.status |= msg.FLAG_DELETED
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
        if dotlock: dotlock.unlock()
        if filelock: filelock.unlock()


class messageSummary(emailaccount.messageSummary):
    def getMessage(self, mbox):
        """Return full text of this message as an email.message object.
        May return None for a non-available message."""
        # TODO: confirm the mailbox hasn't changed
        ifile = open(mbox.path, "r")
        ifile = filerange.Filerange(ifile, self.offset, self.size)
        return mbox.parser.parse(ifile)
