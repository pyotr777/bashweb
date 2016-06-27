#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = 0.2-01

import bottle
import subprocess
import re
import urllib
import os

webint = bottle.Bottle()

# Base folder
try:
    base_folder = os.environ["WEBINT_BASE"]
except:
    web_folder = os.getcwd()+"/webfiles"
# Template file names
html_base = "index.html"
static_folder = web_folder+"/static"

print "Webint v" + str(ver)
print "Base folder  : " + web_folder
print "Base page    : " + web_folder + "/" + html_base
print "Static folder: " + static_folder


# Permitted hosts
accessList = ["localhost","127.0.0.1"]

# Check access origin
def allowAccess():
    remoteaddr = bottle.request.environ.get('REMOTE_ADDR')
    forwarded = bottle.request.environ.get('HTTP_X_FORWARDED_FOR')

    if (remoteaddr in accessList) or (forwarded in accessList):
        return True
    else:
        return False

# Workflow Start
#Display emtpy HTML template with command field.
@webint.route('/')
def show_template():
    if allowAccess():
        pass
    else:
        return "Access denied."
    print "Reading base page "+ html_base
    return bottle.static_file(html_base, root=web_folder)


@webint.route('/<filename>')
def show_html(filename):
    if allowAccess():
        pass
    else:
        return "Access denied."
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)

@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)

bottle.run(webint,host='localhost', port=8080, debug=True)


