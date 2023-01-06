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
import imap
from keycodes import *
from utils import writeLog

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
    def wait(self):
        c = self.win.getch()
        self.win.clear()
        self.win.refresh()
        return c
    def displayAndWait(self):
        self.display()
        return self.wait()


SCROLL_THRESH = 5

class ContentScreen(object):
    """Base class for screens that have scrolling content. The
    screen has a top prompt, a content area, an optional status
    line, and a bottom prompt. It handles some basic one-character
    commands and window resizes. Subclasses must implement
    displayContent() for this to be useful. Set status=None
    to disable status line, else use e.g. "" for empty status"""
    def __init__(self, win, prompt1, prompt2, content, status, helpText):
        writeLog("New ContentScreen")
        self.win = win
        self.content = content
        self.contentLen = 100   # subclass must fix this up
        self.prompt1 = prompt1
        self.prompt2 = prompt2
        self.long_options = None
        self.status = status
        self.helpText = helpText
        self.offset = 0
        self.subwin = None
        # Items below to be filled in by resize
        self.hgt, self.wid = self.win.getmaxyx()
        self.contentY = self.statusY = self.prompt2Y = 0
        self.contentHgt = 0
        self.subwin = None

    def resize(self):
        """Compute the sizes and positions of the content. Create the
        subwindow. This should be called any time the terminal window
        changes size, if the status line is enabled/disabled, and
        before first calling display(),"""
        self.hgt, self.wid = self.win.getmaxyx()
        self.contentY = 2
        self.prompt2Y = self.hgt - 1
        if self.status is None:
            self.contentHgt = self.hgt - 4
        else:
            self.statusY = self.hgt - 2
            self.contentHgt = self.hgt - 5

        # If long_options is specified, steal space to display them
        # from the content window.
        if self.long_options:
            l = len(self.long_options)
            self.long_optionsY = self.contentY + self.contentHgt - l
            self.contentHgt -= l + 1
        self.subwin = self.win.subwin(self.contentHgt,self.wid, self.contentY,0)
        self.subwin.scrollok(True)
        return self

    def display(self):
        """Redisplay everything and flush changes to screen"""
        if not self.subwin:
            self.resize()
        win = self.win

        win.clear()

        win.addstr(0,0, self.prompt1)

        self.displayContent()

        if self.status:
            win.addstr(self.statusY,0, self.status)

        win.addstr(self.prompt2Y,0, self.prompt2)
        self.curspos = curses.getsyx()
        win.refresh()
        return self

    def displayContent(self, line0=0, line1=None):
        """Display the content. This method must be overridden to be
        useful. Write out [line0 line1)."""
        if line1 is None:
            line1 = self.contentHgt
        self.subwin.border()
        self.subwin.addstr(1,1, "Add content [%d %d) offset %d" % (line0, line1, self.offset))
        self.subwin.refresh()
        return self

    def refresh(self):
        """Tell curses to bring screen up to date."""
        self.win.refresh()
        return self

    def setContent(self, content):
        """Replace content. Caller should call refresh() after."""
        self.content = content
        self.displayContent()
        return self

    def setTopPrompt(self, prompt):
        """Replace top prompt. Caller should call refresh() after."""
        self.prompt1 = prompt
        self.win.addstr(0,0, prompt)
        return self

    def setBottomPrompt(self, prompt):
        """Replace bottom prompt. Caller should call refresh() after."""
        self.prompt2 = prompt
        self.win.addstr(self.prompt2Y,0, prompt)
        return self

    def setStatus(self, prompt):
        """Replace status. Caller should call refresh() after."""
        self.status = status
        self.win.addstr(self.statusY,0, prompt)
        return self

    def getOffset(self): return self.offset

    def scrollTo(self, i):
        """Adjust offset to the given value, scrolling if needed.
        Returns True if offset changed, False otherwise (because already
        at the end of the range.)"""
        if i < 0 or i > self.contentLen - self.contentHgt + 1 or i == self.offset:
            return self
        subwin = self.subwin
        offset = self.offset
        delta = i - offset
        # Less than SCROLL_THRESH lines change, scroll and just fill in the gaps
        if i < offset and i >= offset-SCROLL_THRESH:
            # scroll down
            subwin.scroll(delta)
            self.offset = i
            self.displayContent(0, -delta)
        elif i > offset and i < offset+SCROLL_THRESH:
            # scroll up
            subwin.scroll(delta)
            self.offset = i
            self.displayContent(self.contentHgt - delta, self.contentHgt)
        else:
            # Beyond that, complete refresh
            self.offset = i
            self.subwin.clear()
            self.displayContent()
        return self

    def scrollBy(self, i):
        return self.scrollTo(self.offset+i)

    def pageUp(self):
        if self.offset <= 0:
            return self
        self.offset -= self.contentHgt - 1
        if self.offset < 0: self.offset = 0
        self.subwin.clear()
        self.displayContent()
        return self

    def pageDown(self):
        offset = self.offset
        offset += self.contentHgt - 1
        if offset >= self.contentLen:
            return self
        self.offset = offset
        self.subwin.clear()
        self.displayContent()
        return self

    def pageHome(self):
        return self.scrollTo(0)

    def pageEnd(self):
        return self.scrollTo(self.contentLen - self.contentHgt + 1)

    def commonKeys(self, c):
        """Handle common keys that scroll up and down. Return
        False if key was not handled by this method."""
        if c in (ord('\n'), ord('j'), CTRL_N, CTRL_E, curses.KEY_DOWN):
            self.scrollBy(1).refresh()
            return True
        if c in (ord('k'), CTRL_P, CTRL_Y, curses.KEY_UP):
            self.scrollBy(-1).refresh()
            return True
        if c in (ord('>'), CTRL_F, curses.KEY_NPAGE, ord(' ')):
            self.pageDown().refresh()
            return True
        if c in (ord('<'), CTRL_B, curses.KEY_PPAGE):
            self.pageUp().refresh()
            return True
        if c in (ord('^'), curses.KEY_HOME):
            self.pageHome().refresh()
            return True
        if c in (ord('$'), curses.KEY_END):
            self.pageEnd().refresh()
            return True
        if c in (curses.KEY_RESIZE, CTRL_L):
            writeLog("Executing resize")
            self.resize()
            self.display()
            return True
        return False    # didn't use this key

    def wait(self):
        while True:
            c = self.win.getch()
            writeLog("Received key %d" % c)
            if self.commonKeys(c):
                continue
            elif c in (ord('q'), ESC):
                return c
    def displayAndWait(self):
        self.display()
        return self.wait()




class PagerScreen(ContentScreen):
    """Displays text and a prompt. If the user selects '?',
    displays help text. If the user enters a command, returns the keycode
    of that command. Any method that doesn't have a specific
    return value returns self, for chaining."""
    def __init__(self, win, text, prompt1, prompt2, helpText):
        writeLog("New PagerScreen, text:")
        super(PagerScreen,self).__init__(win, prompt1, prompt2, text, None, helpText)
        self.formatted = None

    def resize(self):
        super(PagerScreen,self).resize()
        self.__reformat()
        return self

    def __reformat(self):
        wrapper = textwrap.TextWrapper(width=self.wid-1)
        self.formatted = []
        for line in self.content.split('\n'):
            self.formatted.extend(wrapper.wrap(line) if line else [''])
        self.contentLen = len(self.formatted)

    def displayContent(self, line0=0, line1=None):
        """Display the text subwindow"""
        if line1 is None:
            line1 = self.contentHgt
        offset = self.offset
        subwin = self.subwin

        for i in xrange(line0, line1):
            if i+offset >= self.contentLen:
                break
            subwin.addstr(i,0, toUtf(self.formatted[offset+i]))
        subwin.refresh()
        return self

    def setContent(self, text):
        """Replace text. Caller should call refresh() after."""
        self.content = text
        __reformat(self)
        if self.offset >= self.contentLen:
            self.offset = self.contentLen - 2
        self.displayContent()
        return self



class OptionScreen(ContentScreen):
    """Displays a list of options and a prompt. If the user selects '?',
    displays help text. If the user enters a command, returns the keycode
    of that command. If the user selects an option, returns the numeric
    index into the list. Any method that doesn't have a specific
    return value returns self, for chaining."""
    optKeys = "abcdefghijklmorstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    def __init__(self, win, options, prompt1, prompt2, helpText,
                cmds, long_cmds=None):
        super(OptionScreen,self).__init__(win, prompt1, prompt2, options, "", helpText)
        self.content = options
        self.contentLen = len(options)
        # String of commands. Commands "? \nnp<>^$q" are implied.
        self.cmds = cmds = cmds + "? \nnp<>^$q"
        self.long_cmds = long_cmds
        self.optKeys = "".join([c for c in self.optKeys if c not in cmds])
        self.current = 0
        self.maxopts = 0    # max options that can be displayed

    def resize(self):
        super(OptionScreen,self).resize()
        self.maxopts = min(len(self.optKeys), self.contentHgt)

    def display(self):
        """Redisplay everything"""
        super(OptionScreen,self).display()
        long_cmds = self.long_options
        if long_cmds:
            win = self.win
            cl = self.long_optionsY
            for cmd in long_cmds:
                win.addstr(cl,1, cmd)
                cl += 1
            win.refresh()
        return self

    def displayContent(self, line0=0, line1=None):
        """Display the options subwindow"""
        if line1 is None:
            line1 = self.contentHgt
        subwin = self.subwin
        options = self.content
        offset = self.offset
        current = self.current
        optKeys = self.optKeys
        wid = self.wid

        #writeLog("options: " + str(options))
        for i in xrange(line0, line1):
            if i+offset >= self.contentLen or i >= len(optKeys):
                break
            subwin.addstr(i,1, optKeys[i])
            writeLog("i=%d, i+offset=%d, len(options)=%d" % (i, i+offset, len(options)))
            subwin.addstr(i,3, toUtf(str(options[i+offset])[:wid-4]))
            if i+offset == current:
                subwin.addstr(i,0, '>')
        subwin.refresh()
        return self

    def setContent(self, options):
        """Replace options. Caller should call refresh() after."""
        self.content = options
        self.contentLen = len(options)
        if self.offset >= self.contentLen:
            self.offset = self.contentLen - 2
        if self.current >= self.contentLen:
            self.current = self.contentLen - 1
        self.displayContent()
        subwin.refresh()
        return self

    def getCurrent(self): return self.current

    def moveTo(self, i):
        """Adjust index to the given value, scrolling if needed.
        Returns True if index changed, False otherwise (because already
        at the end of the range.)"""
        if i < 0 or i >= self.contentLen:
            return False
        subwin = self.subwin
        current = self.current
        offset = self.offset
        delta = i - offset      # new position, relative to top of screen
        if delta >= 0 and delta < self.maxopts:
            # just move the caret
            writeLog("just move")
            subwin.addstr(current-offset, 0, ' ')
            subwin.addstr(i-offset, 0, '>')
            subwin.refresh()
            self.current = i
            return True
        elif delta < 0:
            # No point in scrolling since the option letters have to be
            # redrawn either way.
            self.offset = self.current = i
            subwin.clear()
            self.displayContent()
            return True
        else:
            self.current = i
            self.offset = i - self.maxopts + 1
            subwin.clear()
            self.displayContent()
            return True

    def moveBy(self, i):
        return self.moveTo(self.current+i)

    def pageUp(self):
        if self.offset <= 0:
            return False
        self.offset -= self.maxopts - 1
        if self.offset < 0: self.offset = 0
        self.current = self.offset
        self.displayContent()
        return True

    def pageDown(self):
        offset = self.offset
        offset += self.maxopts - 1
        if offset >= len(self.content):
            return False
        self.offset = offset
        self.current = offset
        self.displayContent()
        return True

    def pageHome(self):
        return self.moveTo(0)

    def pageEnd(self):
        return self.moveTo(len(self.content) - 1)

    def commonKeys(self, c):
        """Handle common keys that scroll up and down. Return
        False if key was not handled by this method."""
        if c in (ord('n'), ord(']'), CTRL_N, curses.KEY_DOWN):
            self.moveBy(1)
            return True
        if c in (ord('p'), ord('['), CTRL_P, curses.KEY_UP):
            self.moveBy(-1)
            return True
        if c in (ord('>'), CTRL_F, curses.KEY_NPAGE, ord(' ')):
            self.pageDown()
            return True
        if c in (ord('<'), CTRL_B, curses.KEY_PPAGE):
            self.pageUp()
            return True
        if c in (ord('^'), curses.KEY_HOME):
            self.pageHome()
            return True
        if c in (ord('$'), curses.KEY_END):
            self.pageEnd()
            return True
        if c in (curses.KEY_RESIZE, CTRL_L):
            writeLog("Executing resize")
            self.resize()
            self.display()
            return True
        return False    # didn't use this key

    def isOptionKey(self, c):
        """If this character was one of the optKeys, determine which
        option it represented. Else return -1."""
        if c < 0 or c >= ord('z'):
            return -1
        c = chr(c)
        if c in "\n\r":
            return self.current
        idx = self.optKeys.find(c)
        if idx < 0:
            return idx
        if idx >= self.maxopts:
            return -1
        idx += self.offset
        if idx >= len(self.content):
            return -1
        return idx


class ColumnOptionScreen(OptionScreen):
    """Similar to OptionScreen, but displays multiple values in columns."""
    def __init__(self, win, options, prompt1, prompt2, helpText,
                cmds, long_cmds=None):
        super(ColumnOptionScreen,self).__init__(win, options, prompt1, prompt2, helpText,
                cmds, long_cmds)
        self.cwidths = []

    def resize(self):
        super(ColumnOptionScreen,self).resize()
        hgt, wid = self.win.getmaxyx()
        self.resizeColumns(wid)
        return self

    def resizeColumns(self, wid):
        """Meant to be subclassed."""
        self.cwidths = [(0,wid/2), (wid/2,wid/2)]
        return self

    def displayContent(self):
        """Display the options subwindow"""
        win = self.win
        subwin = self.subwin
        options = self.content
        offset = self.offset
        current = self.current
        optKeys = self.optKeys
        hgt, wid = win.getmaxyx()

        subwin.clear()

        n = min(self.maxopts, len(options) - offset)
        for i in range(n):
            subwin.addstr(i,1, optKeys[i])
            values = options[i+offset].getValues()
            cwidths = self.cwidths
            maxc = len(cwidths)
            subwin.move(i, 3)
            subwin.clrtoeol()
            for j,s in enumerate(values):
                if j < maxc and cwidths[j][1] > 0 and s:
                    subwin.addstr(i,3+cwidths[j][0], toUtf(s[:cwidths[j][1]]))
            if i+offset == current:
                subwin.addstr(i,0, '>')

        subwin.refresh()
        return self


class passwordWindow(object):
    """Tool to read password from user."""
    def __init__(self, parent, region=None):
        """Create password window as a sub-region of the parent window. If
        provided, region is (top,left, height, width). If not specified,
        region is centered in the parent window."""
        if not region:
            hgt, wid = parent.getmaxyx()
            region = (hgt//2-2, 1, 4, wid-2)
        self.win = parent.subwin(region[2],region[3], region[0], region[1])
    def display(self, prompt):
        self.win.clear()
        self.win.border()
        self.win.addstr(1,1, prompt)
        self.win.move(2,1)
        self.win.refresh()
    def read(self):
        writeLog("About to call getstr()")
        try:
            return self.win.getstr()
        except KeyboardInterrupt:
            writeLog("keyboard interrupt")
            return None
        finally:
            writeLog("finally")
            self.win.clear()
            self.win.refresh()
