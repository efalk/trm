#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import curses
import errno
import getopt
import os
import re
import signal
import string
import sys
import textwrap
import time

import emailaccount
import forms
from forms import keystr, getUchar
import imap
from keycodes import *
from utils import writeLog

PY3 = sys.version_info[0] >= 3
if PY3:
    def fromUtf(s):
        return s
    def toUtf(s):
        return s
    unicode = str
    basestring = str
else:
    def fromUtf(s):
        return s.decode("utf8", "replace")
    def toUtf(s):
        # Only unicode (not str) needs encoding
        if isinstance(s, unicode): return s.encode("utf8", "replace")
        else: return s


class ShortMessage(object):
    """Displays a message until the user presses any key. Screen will
    be cleared after, caller will want to move on to the next screen."""
    def __init__(self, win, message):
        self.win = win
        self.message = message
    def display(self):
        self.win.clear()
        self.win.addstr(1,0,self.message)
        self.win.refresh()
        return self
    def wait(self):
        c = self.win.getch()
        self.win.clear()
        self.win.refresh()
        return c
    def displayAndWait(self):
        return self.display().wait()

def HelpScreen(win, text):
    writeLog("New helpScreen(%s)" % text[:100])
    form = TextPagerScreen(win, text, 'Help',
        (("q Exit help", "↑ Up one",   "PGUP < Page up",   "HOME ^ Top"),
         ("? long help", "↓ Down one", "PGDN > Page down", "END  $ Bottom")))
    writeLog("form = %s, calling redraw.refresh" % form)
    form.redraw().refresh()
    while True:
        key = form.getUchar()
        if form.handleKey(key) is None:
            if key == u'?':
                form = None     # We won't be coming back, so dismiss the form
                win.clear()
                win.refresh()
                HelpScreen(win, MAIN_HELP)
                return
            if key == u'q':
                return


SCROLL_THRESH = 5

class ContentScreen(forms.Form):
    """Base class for screens that have scrolling content. The
    screen has a top prompt, a content area, an optional status
    line, and a bottom prompt. It handles some basic one-character
    commands and window resizes. Subclasses must implement
    displayContent() for this to be useful. Set status=None
    to disable status line, else use e.g. "" for empty status
    shortHelp is an array [cols][rows] of short help messages,
    e.g. (("? Help, "q Back"), ("n Next", "< page up"), ("p Prev", "> page down"), ("CR select",))
    """
    def __init__(self, win, content, prompt, shortHelp, status):
        writeLog("ContentScreen.init()")
        super(ContentScreen,self).__init__(win, False)
        self.prompt = prompt
        self.status = status
        self.content = content
        self.contentLen = 100   # subclass must fix this up
        self.shortHelp = shortHelp
        self.busy = False       # user can't interact right now
        # Items below to be filled in by resize
        self.hgt, self.wid = win.getmaxyx()
        self.promptW = self.statusW = self.contentW = self.helpW = None
        self.promptY = self.statusY = self.helpY = 0
        self.contentHgt = 0
        self.contentY = 0
        self.resize()

    def resize(self):
        """Compute the sizes and positions of the content. Create the
        subwindow. Call this after the widgets are added and before
        first display. Call any time the screen size changes.
        Meant to be subclassed. Subclasses should create the content
        widget to match content{Hgt,Y}."""
        self.hgt, self.wid = self.win.getmaxyx()
        writeLog("ContentScreen.resize() %dx%d" % (self.hgt, self.wid))
        # Find the heights of all the regions, content region gets
        # the leftover.
        # Top prompt and status are always 1 line. ShortHelp is typically
        # two lines, but we don't enforce that. One blank line between
        # regions except above status.
        # promptY = 0
        y = 0
        if self.prompt:
            self.promptY = y
            y += 1
        if self.status is not None:
            self.statusY = y
            y += 1
        if y > 0: y += 1        # leave a blank line
        self.contentY = y
        # Start filling from the bottom
        y = self.hgt
        if self.shortHelp:
            y -= len(self.shortHelp)
            self.helpY = y
            y -= 1              # Another blank line
        #writeLog("resize: hgt=%d, len=%d, Y=%d" % (self.hgt, len(self.shortHelp[0]), self.helpY))
        self.contentHgt = y - self.contentY
        #writeLog("hgt=%d, wid=%d, y=%d, 0" % (self.contentHgt,self.wid, self.contentY))

        # Create or update the widgets
        if not self.promptW:
            self.promptW = self.Label(self, 1,-1, self.promptY,0, self.prompt)
        else:
            self.promptW.setSize(1,-1, self.promptY,0)
        if self.status is not None:
            if not self.statusW:
                self.statusW = self.Label(self, 1,-1, self.statusY,0, self.status)
            else:
                self.statusW.setSize(1,-1, self.statusY,0)
        if not self.contentW:
            self._createContent()
        else:
            self._resizeContent()
        if not self.helpW:
            self.helpW = self.ShortHelp(self, len(self.shortHelp),-1, self.helpY,0, self.shortHelp)
        else:
            self.helpW.setSize(len(self.shortHelp),-1, self.helpY,0)
        widgets = [self.promptW, self.statusW, self.contentW, self.helpW]
        widgets = filter(lambda w: w, widgets)
        #writeLog("set widgets %s" % widgets)
        self.setWidgets(widgets)
        return self

    def _createContent(self):
        """Override this in subclasses"""
        writeLog("ContentScreen._createContent() contentW = %s" % self.contentW)
        self.contentW = self.OutputWindow(self, self.contentHgt,-1, self.contentY,0)

    def _resizeContent(self):
        """Override this in subclasses"""
        writeLog("ContentScreen._resizeContent() contentW = %s" % self.contentW)
        self.contentW.setSize(self.contentHgt,-1, self.contentY,0)

    def displayContent(self, line0=0, line1=None):
        """Refresh the main content subwindow. Caller should call refresh() after."""
        self.contentW.displayContent(line0, line1)
        return self

    def setBusy(self, busy):
        """Toggle busy flag. Caller should call refresh()."""
        self.busy = busy
        self.helpW.enable(not busy)
        return self

    def setContent(self, content):
        """Replace content. Caller should call refresh() after."""
        self.content = content
        self.contentW.set(content)
        return self

    def setTopPrompt(self, prompt):
        """Replace top prompt. Caller should call refresh() after."""
        self.prompt = prompt
        self.promptW.set(prompt).refresh()
        return self

    def setShortHelp(self, shortHelp):
        """Replace bottom prompt. Caller should call refresh() after.
        new shortHelp must be the same number of lines as before. Caller
        should call refresh() after."""
        self.shortHelp = shortHelp
        self.helpW.set(shortHelp)
        return self

    def setStatus(self, status):
        """Replace status. Caller should call refresh() after."""
        self.status = status
        self.statusW.set(status)
        self.statusW.refresh()
        return self

    def scrollTo(self, i):
        """Adjust offset to the given value, scrolling if needed.
        Returns True if offset changed, False otherwise (because already
        at the end of the range.)
        DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.scrollTo(i)
        return self

    def moveTo(self, i):
        """Change highlight to item i, scrolling as needed.
        DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.moveTo(i)
        return self

    def scrollBy(self, i):
        """DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.scrollBy(i)
        return self

    def pageUp(self):
        """DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.pageUp()
        return self

    def pageDown(self):
        """DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.pageDown()
        return self

    def pageHome(self):
        """DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.pageHome()
        return self

    def pageEnd(self):
        """DO NOT call this if the content widget doesn't support scrolling."""
        self.contentW.pageEnd()
        return self

    def handleKey(self, key):
        #writeLog("ContentScreen.handleKey(%s)" % key)
        if key == curses.KEY_RESIZE:
            self.resize().redraw()
            return True
        return super(ContentScreen, self).handleKey(key)


class PagerScreen(ContentScreen):
    """Displays an array of text and a prompt.  If the user enters a command,
    returns the keycode of that command. Any method that doesn't
    have a specific return value returns self, for chaining."""
    def __init__(self, win, text, prompt, shortHelp, status=None):
        writeLog("New PagerScreen")
        super(PagerScreen,self).__init__(win, text, prompt, shortHelp, status)
    def _createContent(self):
        writeLog("PagerScreen add Pager widget")
        self.contentW = self.Pager(self, self.contentHgt,-1, self.contentY,0, self.content)


class TextPagerScreen(ContentScreen):
    """Displays text and a prompt.  If the user enters a command,
    returns the keycode of that command. Any method that doesn't
    have a specific return value returns self, for chaining."""
    def __init__(self, win, text, prompt, shortHelp, status=None):
        writeLog("New TextPagerScreen")
        super(TextPagerScreen,self).__init__(win, text, prompt, shortHelp, status)
    def _createContent(self):
        writeLog("PagerScreen add Pager widget")
        self.contentW = self.TextPager(self, self.contentHgt,-1, self.contentY,0, self.content)


class ListScreen(ContentScreen):
    """Displays a selectable array of text and a prompt. Returns the item the user
    selected."""
    def __init__(self, win, text, prompt, shortHelp, status=None):
        writeLog("New ListScreen")
        super(ListScreen,self).__init__(win, text, prompt, shortHelp, status)
    def _createContent(self):
        self.contentW = self.List(self, self.contentHgt,-1, self.contentY,0, self.content)
    def wait(self):
        while True:
            key = self.getUchar()
            rval = self.handleKey(key)
            if type(rval) == int:
                writeLog("User chose item %d" % rval)
                return rval


class OptionScreen(ContentScreen):
    """Displays a selectable array of text and a prompt. Returns the item the user
    selected."""
    def __init__(self, win, text, prompt, shortHelp, cmds, status=None):
        writeLog("New OptionListScreen")
        self.cmds = cmds
        super(OptionScreen,self).__init__(win, text, prompt, shortHelp, status)
    def getCurrent(self):
        return self.contentW.getCurrent()
    def setCurrent(self, idx, row):
        writeLog("OptionScreen.setCurrent(%s,%s)" % (idx, row))
        self.contentW.setCurrent(idx, row).redraw()
        return self
    def getScroll(self):
        return self.contentW.getScroll()
    def moveTo(self, idx):
        self.contentW.moveTo(idx)
        return self
    def getRow(self):
        """Return the row of the currently-selected item or None."""
        current = self.contentW.getCurrent()
        if current is None: return None
        return self.contentW.getCurrent() - self.contentW.getScroll()
    def getDirection(self):
        return self.contentW.getDirection()
    def _createContent(self):
        self.contentW = self.OptionsList(self, self.contentHgt,-1, self.contentY,0, self.content, self.cmds)
    def isOptionKey(self, key):
        return self.contentW.isOptionKey(key)
    def wait(self):
        while True:
            writeLog("This is OptionScreen.wait()")
            key = self.getUchar()
            rval = self.handleKey(key)
            writeLog(" OptionScreen.handleKey(%s) returns %s" % (keystr(key), rval))
            if type(rval) == int:
                writeLog(" User chose item %d" % rval)
                return rval


class ActiveOptionScreen(OptionScreen):
    def __init__(self, win, options, prompt, shortHelp, cmds, status=None):
        writeLog("New OptionListScreen")
        super(ActiveOptionScreen,self).__init__(win, options, prompt, shortHelp, cmds, status)
    def _createContent(self):
        self.contentW = self.ActiveOptionsList(self, self.contentHgt,-1, self.contentY,0, self.content, self.cmds)


class ColumnOptionScreen(OptionScreen):
    """Similar to OptionScreen, but displays multiple values in columns."""
    def __init__(self, win, options, prompt, shortHelp, cmds, status=None):
        super(ColumnOptionScreen,self).__init__(win, options, prompt, shortHelp, cmds, status)
        self.cwidths = []
    def _createContent(self):
        self.contentW = self.ColumnOptionsList(self, self.contentHgt,-1, self.contentY,0, self.content, self.cmds)


class simpleDiagWindow(object):
    """Tool to read string from user."""
    def __init__(self, parent, hgt=None, wid=None, top=None, left=None):
        """Create dialog window as a sub-region of the parent window. If
        provided, region is (top,left, height, width). If not specified,
        region is centered in the parent window."""
        h, w = parent.getmaxyx()
        if not hgt: hgt = h//2-2
        if not wid: wid = w-2
        if not top: top = (h-hgt)//2
        if not left: left = 1
        self.win = parent.subwin(hgt,wid, top,left)
    def display(self, prompt):
        """Display prompt, then move cursor
        to last line in region."""
        hgt, wid = self.win.getmaxyx()
        self.win.clear()
        self.win.border()
        for i,s in enumerate(toUtf(prompt).split('\n')):
            self.win.addstr(i+1,1, s)
        self.win.move(hgt-2,1)
        self.win.refresh()
        return self
    def read(self):
        try:
            curses.echo()
            curses.nocbreak()
            return self.win.getstr()
        except KeyboardInterrupt:
            writeLog("keyboard interrupt")
            return None
        finally:
            self.win.clear()
            self.win.refresh()
            curses.noecho()
            curses.cbreak()


class passwordWindow(simpleDiagWindow):
    """Tool to read password from user."""
    def display(self, prompt):
        return super(passwordWindow, self).display((prompt,))
    def read(self):
        try:
            return self.win.getstr()
        except KeyboardInterrupt:
            writeLog("keyboard interrupt")
            return None
        finally:
            self.win.clear()
            self.win.refresh()
