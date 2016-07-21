#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.2AWS-14"

import bottle
import subprocess
import re
import urllib
import os
import sys
import json
from lxml import etree
import StringIO
from gevent import monkey; monkey.patch_all()
import gevent.queue
import gevent
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket

webint = bottle.Bottle()

# Base folder
try:
    base_folder = os.environ["WEBINT_BASE"]
except:
    web_folder = os.getcwd()+"/webfiles"
# Template file names
html_base = "index.html"
static_folder = web_folder+"/static"
default_block = web_folder+"/default.html"
block_counter = 1

print "Webint v" + str(ver)
print "Base folder  : " + web_folder
print "Base page    : " + web_folder + "/" + html_base
print "Static folder: " + static_folder
print "Default block: " + default_block


# Allowed commands
allowed_commands = []
allowed_commands.append("git\s([a-zA-Z0-9\.])*")
allowed_commands.append("ls\s([a-zA-Z0-9\.\-])*")
allowed_commands.append("echo\s([a-zA-Z0-9\.\-\s])*")
allowed_commands.append("find\s([a-zA-Z0-9\.])*")
allowed_commands.append("pwd")
allowed_commands.append("whoami")
allowed_commands.append("../test.sh")

# Commands patterns have been compiled flag
compiled = False
compiled_dic = {}


def allowCommand(test_command):
    global compiled
    global compiled_dic
    if not test_command:
        return False
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
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,  bufsize=1)
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            yield line,
    proc.wait()


# Now only returns output.
# In the future - analyse output.
def getNext(command, block=default_block):
    global block_counter
    block_counter += 1
    print "Block counter = " + str(block_counter)
    print "Displaying output in " + block
    # Default DIV block transformations
    div_transform_id = "someid"    
    div_block_file = open(block)
    div = div_block_file.read()
    # Replace default IDs with block unique IDs
    div = re.sub(r'NNN',str(block_counter),div)
    # And command
    div = re.sub(r'COMMAND',html_safe(command),div)
    # Replace block number variable i in javascript
    div = re.sub(r'var\s*i\s*=\s*1[;]*',r'var i = '+str(block_counter), div)

    div_block_file.close()
    return div

# Replace symbols that can distroy html test field contents.
def html_safe(command):
    command = command.replace('\\',r'\\\\')
    command = command.replace('"',r'\"')    
    print command
    return command

# Workflow Start
#Display emtpy HTML template with command field.
@webint.route('/')
def show_template():
    global block_counter
    block_counter = 1
    print "Reading base page "+ html_base    
    print "Block counter reset to " + str(block_counter)
    return bottle.static_file(html_base, root=web_folder)


@webint.route('/<filename>')
def show_html(filename):
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)

@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)


@webint.route('/exec/<esc_command:path>')
def exec_command(esc_command='pwd'):
    print "Exec_command " + esc_command
    command = urllib.unquote_plus(esc_command)
    print "Executing " + command
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1)
        with proc.stdout:
            for line in iter(proc.stdout.readline, b''):
                print "* "+ line,
                yield line
        proc.wait()
    except AttributeError as ex:
        yield "Error executing command " + command 
        yield sys.exc_info()[0]
    except:
        yield sys.exc_info()[0]

# Add / replace parts of XML file
@webint.post('/xml/edit/<filepath:path>')
def edit_xml(filepath):
    #path = bottle.request.forms.get('filepath')
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    print >> out, "Received XML request for file " + filepath 
    # Open file
    try:
        f = etree.parse("webfiles/" +filepath)
    except IOError as ex:
        print  >> err, "Error reading file " + "webfiles/" + filepath
        stdout = out.getvalue()
        stderr = err.getvalue()
        out.close()
        err.close()
        return json.dumps({'stdout':stdout, 'stderr':stderr})
    #print  >> out, etree.tostring(f)
    
    keys = bottle.request.forms.keys()
    for key in keys:
        val = bottle.request.forms.get(key)
        print  >> out, "key="+key+" val="+val 
        try:
            node = f.xpath(key)
            node[0].text = val
        except etree.XPathEvalError:
            print >> err, "Wrong path syntax: " + key 
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr})

        except:
            print >> err, sys.exc_info()
            print >> err, "Not found: " + key
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr})
   
    print  >> out, etree.tostring(f) 
    print etree.tostring(f) 
    # Return stdout and stderr
    stdout = out.getvalue()
    stderr = err.getvalue()
    out.close()
    err.close()
    return json.dumps({'stdout':stdout, 'stderr':stderr})


@webint.route('/exe', apply=[websocket])
def exe(ws):
    msg = ws.receive()
    print "Rec: " + msg
    command = urllib.unquote_plus(msg)
    print "Have command " + command + "."
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, shell=True)
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            print line,            
            ws.send(line)
    with proc.stderr:
        for line in iter(proc.stderr.readline, b''):
            print line,            
            ws.send("#STDERR"+line)
    
    proc.wait()
    print "finish"
    next_block=getNext(command)
    ws.send("#NEXT"+next_block)
    print "Next block sent"
    return


bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)


