#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

"""Query the user for imap parameters, return imapAccount object."""

import curses
import errno
import imaplib
import os
import socket
import sys
import time

import forms
import imap
import screens
from forms import keystr
import emailaccount
import mbox
import imap
from keycodes import *
from utils import writeLog, toUtf

PY3 = sys.version_info[0] >= 3
if PY3:
    basestring = str


IMAP_HELP = u"""

 F1            this text
 F2            Guess settings
 ↓ TAB         next field
 ↑ BackTAB     previous field
 CR            accept values and return
 ESC           cancel
 ^L            refresh screen
 ^C            exit trm

Fill in the name of this account and the imap server settings.

The name can be anything you want, but if you use the form
"user@example.com" it will help you remember which email host you're
using and this will provide the "Guess settings" function with
something to go on.

The imap server is the server you read your email from. Your hosting
provider will provide this for you, but commonly it's something
like "mail.example.com" or "imap.example.com".

The port is the network port you connect to. Your hosting proovider
will provide this to you, but it's typically 993 for a TLS connection
or 143 for non-tls (insecure) connections. Leave this blank to let
trm fill this in automatically.

The "Use TLS" checkbox indicates that you should use a TLS (secure)
connection. This is highly recommended if your hosting provider
supports it (they almost all do). (Note: you'll sometimes see the
term "SSL" used. The two terms are interchangeable nowadays.)

Imap login is the login id you use to connect. Your hoosting provider
will provide this for you. It's typically your user id, but may
also be in the form "user@example.com".

Imap password is your login password at the hosting provider. Trm
doesn't save this in a particularly secure way, so you might not
want to provide it here. If you leave it blank, trm will ask for
it whenever you connect to the imap server and won't store it.

Alternatively, press the "Guess settings" button to have trm try
some common settings based on the account name. This can be in the
form "user@example.com" or "user@example.com:port"

Trm is a mail reader only, so there are no smtp settings to deal
with.
"""

form = None
topPrompt = None
textName = None
buttonTest = None
textServer = None
textPort = None
cbTls = None
textLogin = None
textPassword = None
logWin = None

promptText = None

PROMPT = """Enter imap account info. Use the "guess" button to try to
determine server settings automatically."""
PROMPT_COMPACT = """Enter imap account info. F1 for help."""

def getImapAccount(stdscr):
    """Display form, run tests if needed, obtain imap server info
    from the user. Return None on failure or user cancel."""
    global form, topPrompt, promptText, textName, buttonTest
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
    compact = hgt < 34
    if compact:
        row = 0
        col = 0
        lblHgt = 1
        lblRow = 1
        promptText = PROMPT_COMPACT
        nameRow = 3
        buttonRow = 5
        serverRow = 8
        portRow = 9
        tlsRow = 10
        loginRow = 11
        passwdRow = 12
        logRow = 13
    else:
        row = 2
        col = 2
        hgt -= 4
        wid -= 4
        lblHgt = 2
        lblRow = 1
        promptText = PROMPT
        nameRow = 5
        buttonRow = 8
        serverRow = 12
        portRow = 14
        tlsRow = 16
        loginRow = 18
        passwdRow = 20
        logRow = 22

    stdscr.clear()
    stdscr.refresh()
    win = stdscr.derwin(hgt,wid,row,col)
    win.keypad(True)
    form = forms.Form(win)

    topPrompt = form.Label(form, lblHgt,-2, lblRow,2, promptText)
    textName = form.Text(form, 1,40, nameRow,32, u"alice@example.com")
    buttonTest = form.Button(form, 3,0, buttonRow,32, "Guess settings")
    buttonTest.setCallback(makeGuesses, None)
    textServer = form.Text(form, 1,40, serverRow,32, "imap.example.com")
    textPort = form.Text(form, 1,40, portRow,32, "")
    cbTls = form.Checkbox(form, 1,0, tlsRow,32, "Use TLS (recommended)")
    cbTls.set(True)
    textLogin = form.Text(form, 1,40, loginRow,32, "alice")
    textPassword = form.Text(form, 1,40, passwdRow,32, "")
    logWin = form.OutputWindow(form, -4,-2, logRow,1)
    sh1 = form.ShortHelp(form, 2,-2,-3,1,
            (("F1    Help", "DEL delete 1 char", "↑ BTAB Previous", "CR accept"),
             ("F2 ^G Guess", "^U  delete all", "↓ TAB  Next", "ESC cancel")))

    widgets = [topPrompt,
        form.Label(form, 1,30,nameRow,2, "      Name for this account:"),
        form.Label(form, 1,30,nameRow+1,2, "   (e.g. alice@example.com)"),
        textName,
        buttonTest,
        form.Label(form, 1,30,serverRow,2, "                imap server:"),
        textServer,
        form.Label(form, 1,30,portRow,2, "                       port:"),
        textPort,
        cbTls,
        form.Label(form, 1,30,loginRow,2, "                 imap login:"),
        textLogin,
        form.Label(form, 1,30,passwdRow,2, "   imap password (optional):"),
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
        if key == curses.KEY_F1:
            screens.HelpScreen(win, IMAP_HELP)
            form.redraw().refresh()
            continue
        if key == curses.KEY_F2:
            makeGuesses(None, None)
            continue
        if key in (u'\r', u'\n'):
            form.redraw().refresh()
            name = textName.get()
            host = textServer.get()
            port = textPort.get()
            if not port:
                port = 993 if cbTls.get() else 143
            ssltls = "tls" if cbTls.get() else "none"
            user = textLogin.get()
            passwd = textPassword.get()
            return imap.imapAccount(name, host, port, ssltls, user, passwd, "plain")
        if key == ESC:
            return None
        form.handleKey(key)

    return None

topPrompt = None
textName = None
buttonTest = None
textServer = None
textPort = None
cbTls = None
textLogin = None
textPassword = None
logWin = None

def makeGuesses(widget, client):
    topPrompt.clear().set("Trying imap settings. This may take a while. ^C to cancel.").refresh()
    logWin.clear().refresh()
    logWin.write("Trying imap settings. This may take a while. ^C to cancel.\n")
    try:
        emailAddr = textName.get()
        if not emailAddr or u'@' not in emailAddr:
            logWin.write("An email addres is required to guess imap settings.\n")
            return
        logWin.write('Testing email address "%s"\n' % emailAddr)
        user,host,port = parseEmail(emailAddr)
        timeout = 10
        socket.setdefaulttimeout(timeout)

        result = tryServers(host,port)

        if result:
            logWin.write("done, success\n")
            textServer.set(result[0])
            textPort.set(str(result[1]))
            cbTls.set(result[2])
            form.refresh()
        else:
            logWin.write("done, no values found, enter manually\n")
    except KeyboardInterrupt as e:
        logWin.write("Canceled\n")
    finally:
        topPrompt.clear().set(promptText).refresh()

def tryServers(host, port):
    pfxs = ('mail.', 'imap.', 'imap4.', '', 'pop.')
    ss = (True, False)
    rval = None
    for pfx in pfxs:
        for s in ss:
            testhost = pfx + host
            p = port if port else 993 if s else 143
            logWin.write("Trying %s:%d, %sssl ..." % (testhost, p, '' if s else 'no '))
            try:
                if s:
                    srvr = imaplib.IMAP4_SSL(testhost, p)
                else:
                    srvr = imaplib.IMAP4(testhost, p)
            except socket.error:
                logWin.write(' failed to connect\n')
                srvr = None
            if srvr:
                logWin.write(' success\n')
                rval = (testhost, p, s)
                if s:
                    return rval     # Found an SSL connection, our search is done
    return rval


def parseEmail(email, u=None, h=None, p=None):
  '''Extract user, host, port from user@host:port. Return
  user,host,port tuple.'''
  if '@' not in email:
    u = email
    h = p = None
  else:
    parts = email.split('@')
    u = '@'.join(parts[:-1])
    h = parts[-1]
    if ':' in h:
      h,p = h.split(':')
      p = int(p)
  return (u,h,p)
