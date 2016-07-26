#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.3alpha-09"

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
import csv

webint = bottle.Bottle()

# Dictionary for saving varibale set inside executed shell processes
env_vars = dict()

# Variables initialisation
try:
    web_folder = os.environ["WEBINT_BASE"]
except:
    web_folder = os.getcwd()+"/webfiles"

try:
    script_number = os.environ["SCRIPT_NUM"]
except:
    script_number = 1

# Template file names
html_base = "index.html"
static_folder = web_folder+"/static"
default_block = web_folder+"/default.html"
block_counter = 0
WS_alive = False
output_file_handler = 0

command_list=[]
descript_list=[]
block_list=[]
files2remove=[]

# Read command_list, descrition list and block list from tsv file "script.tsv"
with open(static_folder+"/config/script_"+str(script_number)+".tsv", 'r') as script:
    script = csv.reader(script, delimiter='\t')
    i = 0
    for row in script:
        print "row:" + str(row)
        command_list.append(row[0])
        descript_list.append(row[1])
        block_list.append(row[2])
        i = i + 1

print command_list
print descript_list
print block_list


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
    global block_counter
    global WS_alive
    global output_file_handler
    WS_alive = True
    print "WEB SOCKET\talive"
    print "BC_\t" + str(block_counter)

    msg = ws.receive()
    if msg is None or len(msg) == 0:
        print "Null command"
        next_block=getNext()
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    print "Rec: " + msg    
    command = parseCommand(msg)
    print "Have command " + command
    if command.find("#SETVARS") == 0:
        print "setvars"
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
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged_env, bufsize=1, shell=True, executable="/bin/bash")
    
    # Open output file
    output_file_handler = openOutputFile(block_counter)

    # Loop with running process output
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            print "---"
            output(line,ws)
            parse_vars(line)            
    proc.wait()
    
    # Close output file
    output_file_handler.close()

    next_block=getNext()
    ws.send("#NEXT"+next_block)    
    print "Next block sent"
    WS_alive = False
    print "WEB SOCKET\tdead"
    if next_block == "OK":        
        shutdown()
    return


# Now only returns output.
# In the future - analyse output.
def getNext(block=default_block):
    global block_counter
    global block_list
    global static_folder
    global files2remove
    block_counter += 1
    print "BC\t" + str(block_counter)
    if block_counter > len(command_list):
        print "No more commands"
        os.remove
        return "OK"
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
    div = re.sub(r'COMMAND',str(block_counter),div)
    # Discription
    div = re.sub(r'DISCRIPTION',descript_list[block_counter-1],div)
    # Replace block number variable i in javascript
    div = re.sub(r'var\s*i\s*=\s*1[;]*',r'var i = '+str(block_counter), div)
    div_block_file.close()
    # Save block to file blockNNN.html
    outfilename = static_folder + "/block_" + str(block_counter) + ".html"
    print "Write to " + outfilename
    out_block_file = open(outfilename, 'w')
    files2remove.append(outfilename)
    out_block_file.write(div)
    out_block_file.write("\n")
    out_block_file.close()
    return div

# Print line to WS and to block file and to stdout
def output(str, ws):
    global WS_alive
    global output_file_handler
    if WS_alive:
        try:
            ws.send(str)
        except WebSocketError as ex:
            print "Web socket died."
            WS_alive = False;
    print str
    print >> output_file_handler, str

# Open output file 
def openOutputFile(block_counter):
    global static_folder
    global files2remove
    outfilename = static_folder + "/output_" + str(block_counter) + ".txt"
    output_file = open(outfilename, 'w')
    files2remove.append(outfilename)
    print "Write output to " + outfilename
    return output_file


# Get envvars from output lines
def parse_vars(str):
    global env_vars
    m = re.search("([\w/]+)=([\S]+)",str)
    if m is not None and len(m.groups()) == 2:
        env_vars[m.group(1)] = m.group(2)


# Get command from message
# If message contains ";", split it.
# First part should be integer number of command, second part - arguments for the command.
def parseCommand(msg):
    if msg.find(";") > 0:
        parts = msg.split(";")
        command = command_list[int(parts[0]) - 1] + ";" + ";".join(parts[1:])
    else:
        command = command_list[int(msg) - 1]
    return command


# Shutdown server
def shutdown():
    global files2remove
    print "Shutting down"
    # Remove temporary files
    for file in files2remove:
        print "Delete "+file
        os.remove(file)
    pid = os.getpid()
    print "PID\t"+str(pid)
    ps = subprocess.check_output(["ps","ax",str(pid)])
    print ps
    subprocess.check_call(["kill",str(pid)])

bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)
