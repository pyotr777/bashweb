#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.2-02"

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
# Allowed commands
allowed_commands = []
allowed_commands.append("git\s(.)*")
allowed_commands.append("ls\s(.)*")
allowed_commands.append("echo\s(.)*")
allowed_commands.append("find\s(.)*")
allowed_commands.append("pwd")
allowed_commands.append("whoami")

# Commands patterns have been compiled flag
compiled = False
compiled_dic = {}


# Check access origin
def allowAccess():
    remoteaddr = bottle.request.environ.get('REMOTE_ADDR')
    forwarded = bottle.request.environ.get('HTTP_X_FORWARDED_FOR')

    if (remoteaddr in accessList) or (forwarded in accessList):
        return True
    else:
        return False

def allowCommand(test_command):
    global compiled
    global compiled_dic
    print "Checking command "+ test_command
    if not compiled:
        print "Compiling command patterns"
        for command in allowed_commands:
            # print command.pattern_str
            compiled_dic[command] = re.compile(command)
        compiled = True
    for pattern_str in compiled_dic:
        pattern = compiled_dic[pattern_str]
        # print "Checking pattern " + pattern_str
        # print test_command
        if pattern.match(test_command) is not None:
            # print "Command "+test_command+" matched pattern " + pattern_str
            return True
    print "No patterns matched. Command "+test_command+" not allowed."
    return False

# Execute command in shell
# and return its stdout and stderr streams.
def Execute(command) :
    #output = subprocess.check_output(command.split(),stderr=subprocess.STDOUT)
    print "Executing " + command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output = [l.decode('utf8') for l in proc.stdout.readlines()]
    err = [l.decode('utf8') for l in proc.stderr.readlines()]    
    return (output, err)

# Now only returns output.
# In the future - analyse output.
def displayOutput(output):
    print "Displaying output"
    return output





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

@webint.get('/exec/')
def exec_get_command():
    command = bottle.request.query.getunicode("cmd")
    print "CMD: " + str(command)
    if allowAccess():
        pass
    else:
        return "Access denied."
    if allowCommand(command):
        pass
    else:
        return displayOutput("Command not allowed.")
    try:
        # print command.split()
        output, err = Execute(command)
        joined = " ".join(output) + "<span color=red>" + " ".join(err) + "</span>"
        return displayOutput(joined)
    except subprocess.CalledProcessError as ex:
        error = "Error. cmd='"+ " ".join(ex.cmd)+ "' returncode="+ str(ex.returncode)
        return displayOutput(error)
    else:       
        # Read HTML template replacing "" line 
        # with command output.
        return displayOutput(output)


@webint.route('/exec/<esc_command>')
def exec_command(esc_command='pwd'):
    print "Exec_command " + esc_command
    if allowAccess():
        pass
    else:
        return "Access denied."

    command = urllib.unquote_plus(esc_command)    
    print "Parced URL. Have command " + command + "."
    if allowCommand(command):
        pass
    else:
        return "Command not allowed."

    try:
        output = subprocess.check_output(command.split(),stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as ex:
        return "Error. cmd='"+ " ".join(ex.cmd)+ "' returncode="+ str(ex.returncode)
    else:       
        # Read HTML template replacing "" line 
        # with command output.
        return displayOutput(output)


bottle.run(webint,host='localhost', port=8080, debug=True)


