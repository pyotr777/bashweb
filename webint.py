#!/usr/bin/env python

from bottle import Bottle, run, request
import subprocess
import re
import urllib
import os

webint = Bottle()


# Class for allowed commands
class Command(object):
    def __init__(self,pattern_str,transform_rules_files,template_folder):
        self.pattern_str = pattern_str
        self.transform_rules_files = transform_rules_files
        self.template_folder = template_folder



# Templates folder
try:
    template_folder = os.environ["WEBINT_TEMPLATES"]
except:
    template_folder = os.getcwd()+"/templates"
# Template file names
html_template = "index.html"
html_placeholder = "<output_placeholder />"
print "Template folder: " + template_folder
print "HTML template: " + html_template 

# Permitted hosts
accessList = ["localhost","127.0.0.1"]
# Allowed commands
allowed_commands = []
command_instance = Command("git\s(.)*","",template_folder)
allowed_commands.append(command_instance)
command_instance = Command("ls\s(.)*","",template_folder)
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
    html_template_path = os.path.join(template_folder, html_template)
    print "Reading from template file "+ html_template_path
    result = ""
    with open(html_template_path, 'r') as f:
        for line in f:
            if html_placeholder in line:
                result += output
            else:
                result += line
    return result

# Workflow Start
#Display emtpy HTML template with command field.
@webint.route('/')
def show_template():
    if allowAccess():
        pass
    else:
        return "Access denied."
    return replaceInTemplate("")


@webint.route('/hello')
def hello():
    return "Hello World!"

@webint.route('/exec/<esc_command>')
def exec_command(esc_command='pwd'):
    if allowAccess():
        pass
    else:
        return "Access denied."

    URL_str = urllib.unquote_plus(esc_command)
    URL_parts = URL_str.split("&")
    command = ""
    for command_str in URL_parts:
        command_parts = command_str.split("=")
        if command_parts[0] == "cmd":
            command = command_parts[1]
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
        return replaceInTemplate(output)

@webint.route('/myhost')
def display_remote_host():
    return bottle.request.environ.get('REMOTE_ADDR')

run(webint,host='localhost', port=8080, debug=True)

