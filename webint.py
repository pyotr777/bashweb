#!/usr/bin/env python

from bottle import Bottle, run, request
import subprocess
import re
import urllib
import os
import command_class

webint = Bottle()

# Templates folder
template_folder = os.environ['WEBINT_TEMPLATES']
if template_folder is None:
    template_folder = subprocess.check_output(["pwd"],stderr=subprocess.STDOUT)+"/templates"
# Template file names
html_template = "index.html"
html_placeholder = "<output_placeholder/>"


# Permitted hosts
accessList = ["localhost","127.0.0.1"]
# Allowed commands
allowed_commands = []
command_instance = command_class.Command("git\s(.)*","",template_folder)
allowed_commands.append(command_instance)
command_instance = command_class.Command("ls\s(.)*","",template_folder)
allowed_commands.append(command_instance)

# Commands patterns have been compiled flag
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
        for command in allowed_commands:
            compiled_dic[command.pattern_str] = re.compile(command.pattern_str)
        compiled = True
    for pattern_str in compiled_dic:
        pattern = compiled_dic[pattern_str]
        if pattern.match(command) != None:
            print "Command "+command+" matched pattern " + pattern_str
            return True
    print "No patterns matched. Command "+command+" not allowed."
    return False

def replaceInTemplate(output):
    global template_folder
    global html_template
    global html_placeholder
    html_template_path = open(template_folder+"/"+html_template)
    result = ""
    with open(html_template_path, 'r') as f:
        for line in f:
            if html_placeholder in line:
                result += output
            else:
                result += line
    return result

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
        # Read HTML template replacing "" line 
        # with command output.
        return replaceInTemplate(output)

@webint.route('/myhost')
def display_remote_host():
    return bottle.request.environ.get('REMOTE_ADDR')

run(webint,host='localhost', port=8080, debug=True)

