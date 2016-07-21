#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.3alpha-04"

import bottle
import subprocess
import shlex
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

# Dictionary for saving varibale set inside executed shell processes
env_vars = dict()

# Variables initialisation
try:
    web_folder = os.environ["WEBINT_BASE"]
except:
    web_folder = os.getcwd()+"/webfiles"
# Template file names
html_base = "index.html"
static_folder = web_folder+"/static"
default_block = web_folder+"/default.html"
block_counter = 0

command_list=['#SETVARS', 
            'env | grep "KP_"',
            '',
            './webint/disp.sh']

descript_list=["Set envvars",
            "Check env",
            "edit xml",
            "disp"]

block_list=["envvars_block.html",
            "command_block.html",
            "save_to_xml.html",
            "command_block.html"]

env_file = "_env"

print "Webint v" + str(ver)
print "Web folder  : " + web_folder
print "Web page    : " + web_folder + "/" + html_base
print "Static folder: " + static_folder
print "Default block: " + default_block


@webint.route('/')
def show_template():
    global block_counter
    block_counter = 0
    print "Reading base page "+ html_base    
    print "Block counter reset to " + str(block_counter)
    return bottle.static_file(html_base, root=web_folder)


@webint.route('/<filename>')
def show_html(filename):
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)

@webint.route('/next')
def loadNext():
    print "Loading next default block"
    return getNext()

@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)

@webint.route('/exe', apply=[websocket])
def exe(ws):
    global env_vars
    msg = ws.receive()
    if msg is None or len(msg) == 0:
        print "Null command"
        next_block=getNext()
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    #print "Rec: " + msg    
    #command = "./exec_env " + msg 
    command = msg
    #command = urllib.unquote_plus(command)
    #args = shlex.split(command)
    print "Have command " + command
    if command.find("#SETVARS") == 0:
        print "found"
        # Got command with variables in it
        # Save vars into env_vars and return
        assignments = command.split(";")
        print assignments
        for assign in assignments:
            parse_vars(assign)
        next_block=getNext()
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return
    else:
        print "Not found: "+ str(command.find("#SETVARS"))

    init_env = os.environ.copy()
    merged_env = init_env.copy()
    merged_env.update(env_vars) 
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=merged_env, bufsize=1, shell=True, executable="/bin/bash")
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            print line,
            parse_vars(line)
            ws.send(line)
    with proc.stderr:
        for line in iter(proc.stderr.readline, b''):
            print line,            
            ws.send("#STDERR"+line)
    
    proc.wait()
    next_block=getNext()
    ws.send("#NEXT"+next_block)
    print "Next block sent"
    return

# Add / replace parts of XML file
@webint.post('/xml/edit/<filepath:path>')
def edit_xml(filepath):
    #path = bottle.request.forms.get('filepath')
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    print >> out, "Received XML request for file " + filepath 
    # Open file
    filepath=web_folder+"/" +filepath
    try:
        f = etree.parse(filepath)
    except IOError as ex:
        print  >> err, "Error reading file " + filepath
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
    stdout = html_safe(out.getvalue())
    stderr = err.getvalue()
    out.close()
    err.close()
    next_block=getNext()
    print "Next block will be sent"
    return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})



# Now only returns output.
# In the future - analyse output.
def getNext(block=default_block):
    global block_counter
    global block_list
    block_counter += 1
    print "BC\t" + str(block_counter)
    if block_counter > len(command_list):
        print "No more commands"
        os.remove
        return "OK"
    else:
        command = html_safe(command_list[block_counter-1])
        print "Next command is " + command
    if block_counter <= len(block_list):
        block = web_folder+"/" + block_list[block_counter-1]
    print "Displaying output in " + block
    # Default DIV block transformations
    div_transform_id = "someid"    
    div_block_file = open(block)
    div = div_block_file.read()
    # Replace default IDs with block unique IDs
    div = re.sub(r'NNN',str(block_counter),div)
    # And command
    div = re.sub(r'COMMAND',command,div)
    # Discription
    div = re.sub(r'DISCRIPTION',descript_list[block_counter-1],div)
    # Replace block number variable i in javascript
    div = re.sub(r'var\s*i\s*=\s*1[;]*',r'var i = '+str(block_counter), div)
    div_block_file.close()
    return div

s = 5
esc_pairs = [[None] * 2 for y in range(s)]
esc_pairs[0] = ['\\','\\\\'] 
esc_pairs[1] = ['"','&quot;']
esc_pairs[2] = ['<','&lt;']
esc_pairs[3] = ['>','&gt;']
esc_pairs[4] = ["\n","\\n"]


# Replace symbols that can distroy html test field contents.
def html_safe(command):
    for esc in esc_pairs:
        command = command.replace(esc[0],esc[1])
    
    print command
    return command

# Get envvars from output lines
def parse_vars(str):
    global env_vars
    m = re.search("([\w/]+)=([\S]+)",str)
    if m is not None and len(m.groups()) == 2:
        env_vars[m.group(1)] = m.group(2)
        print "Env vars:"
        for v in env_vars:
            print v+" = "+ env_vars[v]



bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)
