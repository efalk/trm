#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

"""Query the user for imap parameters, return imapAccount object."""

import curses
import errno
import getopt
import operator
import os
import re
import signal
import stat
import string
import sys
import time

import forms
import screens
from forms import keystr
import emailaccount
import mbox
import imap
from keycodes import *
from utils import writeLog, loggingEnabled, configGet, configSet, toUtf

PY3 = sys.version_info[0] >= 3
if PY3:
    basestring = str


IMAP_HELP = u"""

Fill in the name of this account and the imap server settings.
Alternatively, press the "Guess settings" button to have trm try
some common settings based on the account name.

Leave port blank to use port 143 or 993 according to the TLS flag.

 F1            this text
 ↓ TAB         next
 ↑ BackTAB     previous
 CR            select current item
 ^L            refresh screen
 ^C            exit trm
 ESC           return to previous screen
"""

textName = None
buttonTest = None
textServer = None
textPort = None
cbTls = None
textLogin = None
textPassword = None
logWin = None

def getImapAccount(stdscr):
    """Display form, run tests if needed, obtain imap server info
    from the user. Return None on failure or user cancel."""
    global textName, buttonTest
    global textServer, textPort, cbTls, textLogin, textPassword
    global logWin

    # Obtain the following info:
    # name = account name, e.g. falk@efalk.org
    # imap = imap server, e.g. imap.example.com
    # imappport = e.g. 993
    # imapconn = e.g. tls
    # imapuser = e.g. falk
    # imappass = e.g. hunter2
    # smtp = e.g. smtp.example.com
    # smtpport = e.g. 587
    # smtpconn = e.g. tls
    # smtpuser = e.g. falk@efalk.org

    hgt,wid = stdscr.getmaxyx()
    wid -= 4

    stdscr.clear()
    stdscr.refresh()
    win = stdscr.derwin(hgt-4,wid-4,2,2)
    win.keypad(True)
    form = forms.Form(win)

    lbl1 = form.Label(form, 2,-2, 2,2, """Enter imap account info. Use the "guess" button to try to
determine server settings automatically.""")
    textName = form.Text(form, 1,40, 5,32, u"alice@example.com")
    buttonTest = form.Button(form, 3,0, 8,32, "Guess settings")
    buttonTest.setCallback(makeGuesses, None)
    textServer = form.Text(form, 1,40, 12,32, "imap@example.com")
    textPort = form.Text(form, 1,40, 14,32, "")
    cbTls = form.Checkbox(form, 1,0, 16,32, "Use TLS (recommended)")
    cbTls.set(True)
    textLogin = form.Text(form, 1,40, 18,32, "alice")
    textPassword = form.Text(form, 1,40, 20,32, "")
    logWin = form.OutputWindow(form, -4,-2, 22,1)
    sh1 = form.ShortHelp(form, 2,-2,-3,1,
            (("F1    Help", "DEL delete 1 char", "↑ BTAB Previous", "CR accept"),
             ("F2 ^G Guess", "^U  delete all", "↓ TAB  Next", "ESC cancel")))

    widgets = [lbl1,
        form.Label(form, 1,30,5,2, "      Name for this account:"),
        form.Label(form, 1,30,6,2, "   (e.g. alice@example.com)"),
        textName,
        buttonTest,
        form.Label(form, 1,30,12,2, "                imap server:"),
        textServer,
        form.Label(form, 1,30,14,2, "                       port:"),
        textPort,
        cbTls,
        form.Label(form, 1,30,18,2, "                 imap login:"),
        textLogin,
        form.Label(form, 1,30,20,2, "   imap password (optional):"),
        textPassword,
        logWin,
        sh1,
        ]
    form.setWidgets(widgets)
    form.redraw().refresh()
    #ic = form.wait()
    while True:
        key = form.getUchar()
        writeLog("received key %s" % keystr(key))
        logWin.write("received key %s\n" % keystr(key))
        if key == curses.KEY_F1:
            screens.HelpScreen(win, IMAP_HELP)
            form.redraw().refresh()
            continue
        if key == curses.KEY_F2:
            makeGuesses(None, None)
            continue
        elif key in (CTRL_L, curses.KEY_F3):
            form.redraw().refresh()
            continue
        form.handleKey(key)

    return None

def makeGuesses(widget, client):
    logWin.clear().refresh()
    logWin.write("making guesses\n")
    time.sleep(3)
    logWin.write("done\n")

