#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = 0.1-03

from bottle import Bottle, run, request, get, static_file
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
    template_folder = os.getcwd()+"/webfiles"
# Template file names
html_template = "index.html"
html_placeholder = "<output_placeholder />"
static_folder = template_folder+"/static"

print "Webint v" + str(ver)
print "Template folder: " + template_folder
print "HTML template: " + html_template 

# Permitted hosts
accessList = ["localhost","127.0.0.1"]
# Allowed commands
allowed_commands = []
allowed_commands.append(Command("git\s(.)*","",template_folder))
allowed_commands.append(Command("ls\s(.)*","",template_folder))
allowed_commands.append(Command("echo\s(.)*","",template_folder))
allowed_commands.append(Command("find\s(.)*","",template_folder))
allowed_commands.append(Command("pwd","",template_folder))
allowed_commands.append(Command("whoami","",template_folder))

# Commands patterns have been compiled flag
compiled = False
compiled_dic = {}


# Check access origin
def allowAccess():
    remoteaddr = request.environ.get('REMOTE_ADDR')
    forwarded = request.environ.get('HTTP_X_FORWARDED_FOR')

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
            compiled_dic[command.pattern_str] = re.compile(command.pattern_str)
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

# Execute command in shell
# and return its stdout and stderr streams.
def Execute(command) :
    #output = subprocess.check_output(command.split(),stderr=subprocess.STDOUT)
    print "Executing " + command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output = [l.decode('utf8') for l in proc.stdout.readlines()]
    err = [l.decode('utf8') for l in proc.stderr.readlines()]    
    return (output, err)


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
    return replaceInTemplate("Hello World!")


@webint.get('/exec/')
def exec_get_command():
    command = request.query.getunicode("cmd")
    print "CMD: " + str(command)
    if allowAccess():
        pass
    else:
        return "Access denied."
    if allowCommand(command):
        pass
    else:
        return replaceInTemplate("Command not allowed.")
    try:
        # print command.split()
        output, err = Execute(command)
        joined = " ".join(output) + "<span color=red>" + " ".join(err) + "</span>"
        return replaceInTemplate(joined)
    except subprocess.CalledProcessError as ex:
        error = "Error. cmd='"+ " ".join(ex.cmd)+ "' returncode="+ str(ex.returncode)
        return replaceInTemplate(error)
    else:       
        # Read HTML template replacing "" line 
        # with command output.
        return replaceInTemplate(output)


@webint.route('/exec/<esc_command>')
def exec_command(esc_command='pwd'):
    print "Exec_command " + esc_command
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
    return request.environ.get('REMOTE_ADDR')

@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    print "Serve file " + filepath + " from " +static_folder
    return static_file(filepath, root=static_folder)

run(webint,host='localhost', port=8080, debug=True)

