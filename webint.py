#!/usr/bin/env python

from bottle import Bottle, run, request
import subprocess
import re
import urllib

webint = Bottle()

# Permitted hosts
accessList = ["localhost","127.0.0.1"]
allowedCommands = ["git\s(.)*", "ls\s(.)*"]
compiled = False

# Check access origin
def allowAccess():
    remoteaddr = request.environ.get('REMOTE_ADDR')
    forwarded = request.environ.get('HTTP_X_FORWARDED_FOR')

    if (remoteaddr in accessList) or (forwarded in accessList):
        return True
    else:
        return False

def allowCommand(command):
    global compiled
    compiled_dic = {}
    print "Checking command "+ command
    if not compiled:
        print "Compiling command patterns"
        for pattern_str in allowedCommands:
            compiled_dic[pattern_str] = re.compile(pattern_str)

        compiled = True
    for pattern_str in compiled_dic:
        pattern = compiled_dic[pattern_str]
        if pattern.match(command) != None:
            print "Command "+command+" matched pattern " + pattern_str
            return True
    print "No patterns matched. Command "+command+" not allowed."
    return False


@webint.route('/')
@webint.route('/hello')
def hello():
    return "Hello World!"

@webint.route('/exec/<esc_command>')
def exec_command(esc_command='pwd'):
    if allowAccess():
        pass
    else:
        return "Access denied."

    command = urllib.unquote_plus(esc_command)

    if allowCommand(command):
        pass
    else:
        return "Command not allowed."

    try:
        output = subprocess.check_output(command.split(),stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as ex:
        return "Error. cmd='"+ " ".join(ex.cmd)+ "' returncode="+ str(ex.returncode)
    else:        
        return "<html>\n<pre>\n"+output+"</pre>\n</html>"

@webint.route('/myhost')
def display_remote_host():
    return bottle.request.environ.get('REMOTE_ADDR')

run(webint,host='localhost', port=8080, debug=True)

