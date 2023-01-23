#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import curses
import curses.ascii
import errno
import getopt
import os
import re
import signal
import string
import sys
import textwrap
import time

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


class Form(object):
    """Display a form for the user to fill out. Takes a list
    of Widget subclasses, displays them, and returns when one
    of the callbacks signals it."""

    class Widget(object):
        def __init__(self, form, hgt,wid, row,col):
            self.form = form
            self.hgt = hgt
            self.wid = wid
            self.row = row
            self.col = col
            self.win = None
            self.enabled = True
            self.resize()
        def resize(self):
            """Handle size changes. Recompute whatever needs
            computing. Allocate subwindow."""
            self.win = self.form.win.derwin(self.hgt,self.wid, self.row,self.col)
            return self
        def redraw(self):
            """Redraw the widget."""
            return self
        def refresh(self):
            self.win.refresh()
            return self
        def enable(self, enabled=True):
            self.enabled = enabled
            return self.redraw()
        def canFocus(self):
            """Return False if don't want focus."""
            return False
        def takeFocus(self):
            """Notified that gained focus."""
            return self
        def loseFocus(self):
            """Notified that lost focus."""
            return self
        def placeCursor(self, row,col, win=None):
            """Place the cursor at the specific position."""
            # You'd think that self.win.move() would do the trick, but
            # apparently not.
            if not win: win = self.win
            y,x = win.getbegyx()
            row += y
            col += x
            self.form.stdscr.move(row,col)
        def keystroke(self, key):
            """Return False if not interested in this key. Key may
            be an int keycode, or unicode character"""
            return False

    class Label(Widget):
        def __init__(self, form, hgt,wid, row,col, label):
            super(Form.Label,self).__init__(form, hgt,wid, row,col)
            self.label = toUtf(label)
        def redraw(self):
            win = self.win
            win.clear()
            # TODO: truncate line length correctly
            win.addnstr(0,0, self.label, (self.wid-1)*self.hgt)
            return self
        def set(self, s):
            """Set contents of label. Caller should call refresh()"""
            self.label = toUtf(s)
            self.redraw()
            return self
        def __repr__(self):
            return '<Label "%s">' % toUtf(self.label)

    class Text(Widget):
        def __init__(self, form, hgt,wid, row,col, default=u""):
            self.buffer = list(default)
            super(Form.Text,self).__init__(form, hgt,wid, row,col)
            self.scroll = 0
        def resize(self):
            hgt = self.hgt
            wid = self.wid
            self.win = win = self.form.win.derwin(hgt,wid, self.row,self.col)
            if hgt < 3:
                self.textwin = self.win
                self.textwid = wid
            else:
                self.textwin = self.win.derwin(hgt-2, wid-2, 1,1)
                self.textwid = wid-2
            self.curspos = len(self.buffer)
        def set(self, s):
            """Set contents of text field. Caller should call refresh()"""
            self.buffer = list(s)
            self.scroll = 0
            self.curspos = len(self.buffer)
            self.redraw()
            return self
        def redraw(self):
            # If height is 3 or more, add a border
            if self.hgt >= 3:
                self.win.border()
            self.__draw()
            self.__placeCursor()
            return self
        def canFocus(self):
            return True
        def takeFocus(self):
            curses.curs_set(1)
            self.__placeCursor()
            return self
        def loseFocus(self):
            return self
        def keystroke(self, k):
            """I wish I could use getstr() for this, but I need to
            end input on characters other than newline. Tab, backtab,
            arrow keys, etc. all end input. Basically, only printing
            characters are accepted. Also, under Python 2, there's no
            way to receive unicode characters other than to decode them
            manually."""
            win = self.textwin
            if isinstance(k, int):      # Keycode
                return False            # At present, we're not interested in any of these
            else:
                writeLog("character %#o" % ord(k))
                if printable(k):
                    writeLog("printable: %c" % k)
                    wid = self.textwid
                    self.buffer.append(k)
                    l = len(self.buffer)
                    if l > wid-1: self.scroll = l - wid + 1
                    self.__draw()
                    self.__placeCursor()
                    win.refresh()
                    return True
                if k == u'\177':
                    writeLog("del")
                    if self.buffer:
                        wid = self.textwid
                        del self.buffer[-1]
                        l = len(self.buffer)
                        if l >= wid-1: self.scroll = l - wid + 1
                        self.textwin.clear()
                        self.__draw()
                        win.refresh()
                    return True
                if k == "\25":
                    writeLog("^U")
                    self.buffer = []
                    self.scroll = 0
                    self.textwin.clear()
                    self.__draw()
                    win.refresh()
                    return True
            return False
        def __placeCursor(self):
            """Put the cursor where it belongs."""
            col = len(self.buffer) - self.scroll
            self.placeCursor(0, col, self.textwin)
        def __draw(self):
            b = u''.join(self.buffer[self.scroll:])
            wid = self.textwid - 1
            self.textwin.attrset(curses.A_UNDERLINE)
            self.textwin.addstr(0,0, " "*wid)
            self.textwin.addnstr(0,0, toUtf(b), wid)
        def __repr__(self):
            return '<Text "%s">' % toUtf(u"".join(self.buffer))

    class Button(Widget):
        """Button widget. Height should be 3 or more. Set width to 0
        to have it computed from the label. Set the callback to
        have something done when user activates (by pressing space)."""
        def __init__(self, form, hgt,wid, row,col, label):
            if wid == 0: wid = len(label) + 4
            super(Form.Button,self).__init__(form, hgt,wid, row,col)
            self.label = label
            self.enabled = True
            self.focused = False
            self.activated = False
            self.callback = None
            self.client = None
        def setCallback(self, callback, client):
            self.callback = callback
            self.client = client
            return self
        def redraw(self):
            # If height is 3 or more, add a border
            if not self.enabled:
                self.win.attrset(curses.A_DIM)
            self.win.border()
            if not self.enabled:
                self.win.attrset(curses.A_DIM)
            elif self.activated:
                self.win.attrset(curses.A_STANDOUT)
            elif self.focused:
                self.win.attrset(curses.A_BOLD)
            self.win.addstr(self.hgt/2,1, '>' if self.focused else ' ')
            self.win.addnstr(self.hgt/2,2, toUtf(self.label), self.wid-4)
            self.win.addstr(self.hgt/2,self.wid-2, '<' if self.focused else ' ')
            self.win.attrset(curses.A_NORMAL)
            return self
        def activate(self, doCallback=True):
            """Called when button pressed."""
            self.activated = True
            self.redraw().refresh()
            if doCallback:
                if self.callback:
                    self.callback(self, self.client)
                else:
                    time.sleep(0.5)
            self.activated = False
            self.redraw().refresh()
            return self
        def canFocus(self):
            return True
        def takeFocus(self):
            curses.curs_set(0)
            self.focused = True
            self.redraw().refresh()
            return self
        def loseFocus(self):
            self.focused = False
            self.redraw().refresh()
            return self
        def keystroke(self, k):
            """k is either a unicode character, or an int keycode."""
            if isinstance(k, int):
                return False            # At present, we're not interested in any of these
            else:
                if k == ' ':
                    if self.enabled:
                        self.activate()
                    return True
            return False
        def __repr__(self):
            return '<Button "%s">' % toUtf(self.label)

    class Checkbox(Button):
	"""Checkbox widget. Set width to 0 to have it computed from
	the label. Set the callback to have something done when
	user activates (by pressing space). Obtain current state
        with getChecked()"""
        uncheckMark = "☐"
        checkMark = "✓"
        def __init__(self, form, hgt,wid, row,col, label):
            if wid == 0: wid = len(label) + 4
            super(Form.Checkbox,self).__init__(form, hgt,wid, row,col, label)
            self.checked = False
        def redraw(self):
            # If height is 3 or more, add a border
            if not self.enabled:
                self.win.attrset(curses.A_DIM)
            elif self.activated:
                self.win.attrset(curses.A_STANDOUT)
            elif self.focused:
                self.win.attrset(curses.A_BOLD)
            self.win.addstr(self.hgt/2,0, '>' if self.focused else ' ')
            self.win.addnstr(self.hgt/2,1, toUtf(self.label), self.wid-4)
            self.win.addstr(self.hgt/2,self.wid-2, self.checkMark if self.checked else self.uncheckMark)
            #self.win.addstr(self.hgt/2,self.wid-2, '!' if self.checked else '.')
            self.win.attrset(curses.A_NORMAL)
            return self
        def set(self, checked):
            self.activate(checked, False)
        def activate(self, checked, doCallback=True):
            """Called when button pressed."""
            self.checked = checked
            self.activated = True
            self.redraw().refresh()
            if doCallback:
                if self.callback:
                    self.callback(self, self.client)
            self.activated = False
            self.redraw().refresh()
            return self
        def keystroke(self, k):
            """k is either a unicode character, or an int keycode."""
            if isinstance(k, int):
                return False            # At present, we're not interested in any of these
            else:
                if k == ' ':
                    if self.enabled:
                        self.activate(not self.checked)
                    return True
            return False
        def __repr__(self):
            return '<Button "%s">' % toUtf(self.label)

    class ShortHelp(Widget):
	"""Display an array of help prompts. Typically placed at
	the bottom of the form. Typically two lines high. Set any
        of hgt,wid, row,col to None to take the default values, which
        will place the widget at the bottom of the form, filling its
        width. Height to be determined by the first column of shortHelp.

	shortHelp is an array [cols][rows] of short help messages, e.g.
        (("? Help, "q Back"), ("n Next", "< page up"), ("p Prev", "> page down"), ("CR select",))

	This widget does not respond to user input.  Disable to
	make invisible.
        """
        def __init__(self, form, hgt,wid, row,col, shortHelp):
            formhgt, formwid = form.win.getmaxyx()
            if form.border:
                if hgt is None: hgt = len(shortHelp[0])
                if row is None: row = formhgt - hgt - 1
                if col is None: col = 1
                if wid is None: wid = formwid - col - 1
            else:
                if hgt is None: hgt = len(shortHelp[0])
                if row is None: row = formhgt - hgt
                if col is None: col = 0
                if wid is None: wid = formwid - col
            super(Form.ShortHelp,self).__init__(form, hgt,wid, row,col)
            self.shortHelp = shortHelp
        def resize(self):
            """Compute the sizes and positions of the content. No need
            for a subwindow."""
            return self
        def redraw(self):
            """Display the short help at the bottom of the screen. Items
            that won't fit are discarded, so put the least important items
            at the end."""
            shortHelp = self.shortHelp
            # Compute column widths
            wid = self.wid
            cwids = map(max, [map(len, x) for x in shortHelp])
            cwid = sum(cwids)
            pad = max((wid - cwid) // (len(cwids)-1), 2) if len(cwids) >= 2 else 0
            x = 0
            win = self.form.win
            if not self.enabled:
                win.attrset(curses.A_INVIS)
            for i,col in enumerate(shortHelp):
                cw = cwids[i]
                if x + cw > wid:
                    break
                y = self.row
                for s in col:
                    win.addstr(y,x+self.col, s)
                    y += 1
                x += cw + pad
            if not self.enabled:
                win.attrset(curses.A_NORMAL)
            return self
        def refresh(self):
            self.form.win.refresh()
            return self

    class ScrollWindow(Widget):
	"""Create a subwindow to which text can be sent. Also acts
        as a file-like object."""
        def __init__(self, form, hgt,wid, row,col, border=True):
            self.border = border
            super(Form.ScrollWindow,self).__init__(form, hgt,wid, row,col)
        def resize(self):
            self.win = self.form.win.derwin(self.hgt,self.wid, self.row,self.col)
            if self.border:
                self.subwin = self.win.derwin(self.hgt-2,self.wid-2, 1,1)
            else:
                self.subwin = self.win
            self.subwin.scrollok(True)
            return self
        def redraw(self):
            """Display the short help at the bottom of the screen. Items
            that won't fit are discarded, so put the least important items
            at the end."""
            if self.border:
                self.win.border()
            return self
        def refresh(self):
            self.subwin.refresh()
            return self
        def clear(self):
            """Clear the subwindow, caller should call refresh()"""
            self.subwin.clear()
            self.subwin.move(0,0)
            return self
        def write(self, s):
            self.subwin.addstr(toUtf(s))
            self.subwin.refresh()
            return self


    def __init__(self, stdscr, win, border=True):
        self.stdscr = stdscr
        self.win = win
        self.border = border
        self.focus = None          # index into widgets of widget with focus
        self.widgets = []
    def setWidgets(self, widgets):
        """Set the list of widgets. Caller should call redraw()
        and refresh() after."""
        self.widgets = widgets
        self.focus = self._searchFocus(0,1)
    def addWidgets(self, widgets):
        """Extend the list of widgets. Caller should call redraw()
        and refresh() after."""
        self.widgets.extend(widgets)
    def redraw(self):
        if self.border:
            self.win.border()
        if self.widgets:
            for widget in self.widgets:
                widget.redraw()
            self.widgets[self.focus].takeFocus()
        return self
    def setFocus(self, w):
        """Explicitly set the focus widget. w is a Widget or index."""
        f = self.focus
        if isinstance(w, Form.Widget):
            try:
                w = self.widgets.index(w)
            except:
                w = None
        if w == f:
            return self
        if f is not None:
            self.widgets[f].loseFocus()
        self.focus = w
        if w is not None:
            self.widgets[w].takeFocus()
        return self
    def nextFocus(self):
        """Advance focus"""
        w = self._searchFocus(self.focus+1, 1)
        self.setFocus(w)
        self.win.refresh()
        return self
    def previousFocus(self):
        """Move focus back"""
        w = self._searchFocus(self.focus-1, -1)
        self.setFocus(w)
        self.win.refresh()
        return self
    def _searchFocus(self, start, increment):
        """Starting with start, look for a widget that will accept
        focus. Return the index of that widget, or None. increment
        is +1 or -1"""
        l = len(self.widgets)
        start %= l
        for i in range(l):
            if self.widgets[start].canFocus():
                return start
            start = (start+increment)%l
        return None
    def getUchar(self):
        """Return either a unicode character of an integer keycode."""
        return getUchar(self.stdscr)
    def handleKey(self, key):
        """Handle this key. Pass an int keycode or unicode character."""
        if isinstance(key, int):
            if key in (KEY_TAB, curses.KEY_DOWN):
                self.nextFocus()
                return True
            if key in (curses.KEY_BTAB, curses.KEY_UP):
                self.previousFocus()
                return True
            if key == CTRL_L:
                self.redraw().refresh()
                return True
        else:
            if key in ("\t\r\n"):
                self.nextFocus()
                return True
            if key == '\f':
                self.redraw().refresh()
                return True
        # We didn't want it, do any of the widgets?
        if self.widgets[self.focus].keystroke(key):
            return True
        return False    # didn't use this key
    def wait(self):
        """Process keystrokes until encounter one we don't want,
        then return it. This class is different from others: the
        return value will either be int for a keycode, or a unicode
        character"""
        while True:
            key = getUchar(self.stdscr)
#            if isinstance(key, int):
#                writeLog("Received key %s %o" % (type(key), key))
#            else:
#                writeLog("Received key %s %o" % (type(key), ord(key)))
            if not self.handleKey(key):
                return key

    def refresh(self):
        self.win.refresh()


# Version-dependent utilities

if PY3:
    def getUchar(window):
        """Return one wide character or one keycode."""
        return window.get_wch()
    def printable(c):
        return s.isprintable()
else:
    __uchar_buffer = ""
    def getUchar(window):
        """Return one unicode character or one int keycode.
        Only handles UTF-8."""
        # TODO: handle other encodings
        # TODO: timeout on malformed input
        ic = window.getch()
        if curses.ascii.isascii(ic):
            return unichr(ic)
        elif ic >= 0400:        # curses keycode
            return ic
        else:                   # Collect characters until decode() doesn't fail
            __uchar_buffer = chr(ic)
            while True:
                ic = window.getch()
                if curses.ascii.isascii(ic):
                    # should not happen, abandon the buffer
                    return unichr(ic)
                elif ic >= 0400:
                    # should not happen, abandon the buffer
                    return ic
                else:
                    __uchar_buffer += chr(ic)
                    try:
                        # TODO: preferred encoding
                        return __uchar_buffer.decode('utf-8')
                    except UnicodeError as e:
                        if len(__uchar_buffer) >= 4:
                            return u"?"
                        # otherwise, try with more characters
    def printable(c):
        # See https://en.wikipedia.org/wiki/Unicode_control_characters
        # Only works for ascii for now
        if c < ' ': return False
        if c <= '\176': return True  # most common case
        c = ord(c)
        for range in [ (0x007F,0x009F), (0x2000,0x200F), (0x2028,0x202F),
                       (0x205F,0x206F), (0x3000,0x3000), (0xFEFF,0xFEFF),]:
            if c >= range[0] and c <= range[1]:
                return False
        return True


