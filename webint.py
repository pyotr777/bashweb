#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.4alpha-1"

import bottle
import subprocess
import shlex
import re
import string
import urllib
import os
import glob
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
import random
from string import ascii_uppercase, digits
import shutil
from time import sleep

webint = bottle.Bottle()

# Dictionary for saving varibale set inside executed shell processes
env_vars = dict()

# Variables initialisation
try:
    web_folder = os.environ["WEBINT_BASE"]
except:
    web_folder = os.getcwd()+"/webfiles"

try:
    script_number = os.environ["WEBINT_SCRIPT_NUM"]
except:
    script_number = 1

# Template file names
html_base = "index.html"
static_folder = web_folder+"/static"
default_block = web_folder+"/default.html"
block_counter = 0
WS_alive = False

try:
    session = os.environ["WEBINT_SESSION"]
except:
    session=""


command_list=[]
descript_list=[]
block_list=[]
files2remove=[]

# CONFIGURATION (workflow) initialisation
# Read command_list, descrition list and block list from tsv file "script.tsv"
with open(static_folder+"/config/script_"+str(script_number)+".tsv", 'r') as script:
    script = csv.reader(script, delimiter='\t')
    i = 0
    for row in script:
        print "row:" + str(row)
        block_list.append(row[0])
        command_list.append(row[1])
        descript_list.append(row[2])
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
    global session

    if bottle.request.query is None or bottle.request.query.session is None or len(bottle.request.query.session)<1:
        session = ''.join([random.choice(ascii_uppercase + digits) for n in xrange(8)])
        print "SESSION\t"+session
        return start_session()
    else:
        session = bottle.request.query.session
        print "have session "+ session
        return attach_session(session)

def attach_session(session):
    global block_counter
    global static_folder
    sd = session_dir(session)
    print "Attach to  " + session
    if not os.path.isdir(sd):
        print "Creating session folder " + sd
        os.makedirs(sd)
        return show_index()
    else:
        print "Return index.html"
        page = show_index()
        print ""
        print "Reading block files"
        br_counter = 0
        for block_fname in glob.glob(os.path.join(session_dir(session),"block_*.html")):
            br_counter = br_counter + 1
            print "Reading " + block_fname
            block_f = open(block_fname,'r')
            block = block_f.read()
            page = page + block
            block_f.close()
            # Read output
            output_fname = string.replace(block_fname,'block_','output_')
            output_fname = string.replace(output_fname,'.html','.txt')
            print "Looking for "+ output_fname
            if os.path.isfile(output_fname):
                print "Found "+output_fname
                output_f = open(output_fname,'r')
                output = output_f.read()
                output = html_safe(output)
                output_f.close()
                page = page + "\n<div class=\"displayblock\">" + output + "\n</div>\n"
        # Synchronise counters for this webint instance and browser to number of blocks in session folder
        if br_counter > block_counter:
            block_counter = br_counter
            print "BC updated to " + str(block_counter)
        print "Set block_counter in browser to " + str(br_counter)
        # Replace block number variable i in javascript
        page = re.sub(r'var\s*block_counter\s*=\s*1[;]*',r'var block_counter = '+str(br_counter)+";", page)
        # Deactivate index.html (prevent loading next block again)
        page = re.sub(r'var\s*active\s*=\s*1[;]*',r'var active = 0;', page)
        page = page + "\n<script>block_counter = "+str(br_counter)+";\n"
        page = page + "\nconsole.log(\"BC=\"+block_counter);</script>\n"
        return page

# Return session folder path
def session_dir(session):
    return os.path.join(web_folder,"sessions",session)


# Try to read from saved output file
def read_output(session,counter):
    # Read output
    output_fname = os.path.join(session_dir(session),"output_"+counter+".txt")
    if os.path.isfile(output_fname):
        print "OUTPUT FOUND in "+output_fname
        output_f = open(output_fname,'r')
        output = output_f.read()
        output_f.close()
        return output
    else:
        print "Not found " + output_fname
    return False

def start_session():
    global block_counter
    global session
    block_counter = 0
    page = "start_session.html"
    print "Block counter reset to " + str(block_counter)
    file_name = web_folder+"/" + page
    print "Reading " + file_name
    # Default DIV block transformations
    start_file = open(file_name)
    block = start_file.read()
    # Replace default IDs with block unique IDs
    block = re.sub(r'SESSION',session,block)
    start_file.close()
    return block

def show_index():
    global block_counter
    global session
    #block_counter = 0
    print "Reading base page "+ html_base
    #print "Block counter reset to " + str(block_counter)
    index_filename = os.path.join(web_folder,html_base)
    index_f = open(index_filename)
    index = index_f.read()
    index_f.close()
    return index


@webint.route('/<filename>')
def show_html(filename):
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)

@webint.route('/next')
def loadNext():
    global block_counter
    print "Loading next block"
    # Check browser block counter
    if hasattr(bottle.request.query, 'counter'):
        b_counter = bottle.request.query.counter
        if b_counter is not None:
            print "have browser counter " + b_counter
            br_counter = int(b_counter)
            while br_counter <= block_counter:
                # Check block file
                block = read_block(session,b_counter)
                if block:
                    next_b = getNext(b_counter)
                    return block + next_b
                else:
                    print "No saved block found"
                br_counter=br_counter+1
    else:
        print "Counter not in query"
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
    execute_command = True
    print "Session="+session
    WS_alive = True
    print "WEB SOCKET\talive"
    print "BC(server)\t" + str(block_counter)
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

    # Open output file
    output_file_handler = openOutputFile(block_counter)

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
        output_file_handler.close()
        return

    if execute_command:
        init_env = os.environ.copy()
        merged_env = init_env.copy()
        merged_env.update(env_vars)
        print "Exectuing "+command
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged_env, bufsize=1, shell=True, executable="/bin/bash")

        # Loop with running process output
        with proc.stdout:
            for line in iter(proc.stdout.readline, b''):
                output(line,ws,output_file_handler)
                parse_vars(line)
                sleep(0.1)
        proc.wait()
    # Close output file
    output_file_handler.close()

    next_block=getNext()
    ws.send("#NEXT"+next_block)
    print "Next block sent"
    WS_alive = False
    print "WEB SOCKET\tdead\n====="
    if next_block == "OK":
        shutdown()
    return

# Add / replace parts of XML file
@webint.post('/xml/edit/<command_n>')
def edit_xml(command_n):
    next_block=getNext()
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    # Get file path
    filepath = parseCommand(command_n)
    print "Editing "+filepath
    # Open file
    if filepath.find("/") != 0:
        filepath = web_folder+"/" +filepath
    # Read file
    try:
        f = etree.parse(filepath)
    except IOError as ex:
        print  >> err, "Error reading file " + filepath
        stdout = out.getvalue()
        stderr = err.getvalue()
        out.close()
        err.close()
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})

    keys = bottle.request.forms.keys()
    for key in keys:
        val = bottle.request.forms.get(key)
        #print  >> out, "key="+key+" val="+val
        try:
            node = f.xpath(key)
            node[0].text = val
        except etree.XPathEvalError:
            print >> err, "Wrong path syntax: " + key
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})

        except:
            print >> err, sys.exc_info()
            print >> err, "Not found: " + key
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})

    print etree.tostring(f)
    # Save to file
    try:
        fwrt = open(filepath,'w')
    except IOError as ex:
        print  >> err, "Error writing to file " + filepath
        stdout = out.getvalue()
        stderr = err.getvalue()
        out.close()
        err.close()
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})

    print >> fwrt, etree.tostring(f)
    fwrt.close()
    print "Wrote XML to " + filepath
    try:
        frd = open(filepath,'r')
    except IOError as ex:
        print  >> err, "Error reading file " + filepath
        stdout = out.getvalue()
        stderr = err.getvalue()
        out.close()
        err.close()
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})

    new_xml = html_safe(frd.read())
    frd.close()
    print >> out, new_xml

    # Open output file
    output_file_handler = openOutputFile(block_counter-1)  # Decrement beacuse getNext() called before this point
    print >> output_file_handler, new_xml,
    output_file_handler.close()

    # Return stdout and stderr
    stdout = out.getvalue()
    print "Stdout:" + stdout
    stderr = err.getvalue()
    out.close()
    err.close()

    outputXML = json.dumps({'stdout':stdout, 'stderr':stderr, 'next': next_block})
    return outputXML



# Now only returns output.
# In the future - analyse output.
def getNext(counter=None):
    global block_counter
    global block_list
    global static_folder
    global files2remove
    global session
    print counter
    if counter is None:
        print "no counter in getNext"
        block_counter += 1
        counter = block_counter
        print "counter set to " + str(counter)
    else:
        counter = int(counter)
        if counter > block_counter:
            block_counter += 1
            print "block_counter shoud be equal to counter\t"+str(block_counter)+"\t" + str(counter)

    print "Get next ("+str(counter)+")"
    print "BC\t" + str(block_counter)
    if counter > len(command_list):
        print "No more commands"
        os.remove
        return "OK"
    if counter <= len(block_list):
        block = web_folder+"/" + block_list[counter-1]
    print "Use " + block
    # Default DIV block transformations
    div_transform_id = "someid"
    div_block_file = open(block)
    div = div_block_file.read()
    # Replace default IDs with block unique IDs
    div = re.sub(r'NNN',str(counter),div)
    # And command
    div = re.sub(r'COMMAND',str(counter),div)
    # Discription
    div = re.sub(r'DISCRIPTION',descript_list[counter-1],div)
    # Replace block number variable i in javascript
    #div = re.sub(r'var\s*i\s*=\s*1[;]*',r'var i = '+str(counter), div)
    div_block_file.close()
    # Save block to file blockNNN.html
    outfilename = os.path.join(session_dir(session),"block_" + str(counter) + ".html")
    if not os.path.isfile(outfilename):
        print "Write to " + outfilename
        out_block_file = open(outfilename, 'w')
        files2remove.append(outfilename)
        out_block_file.write(div)
        out_block_file.write("\n")
        out_block_file.close()
    return div

# Print line to WS and to block file and to stdout
def output(str, ws, output_file_handler):
    global WS_alive
    if WS_alive:
        try:
            ws.send(str)
        except WebSocketError as ex:
            print "Web socket died."
            WS_alive = False;
    print str,
    print >> output_file_handler, str,

# Open output file
def openOutputFile(block_counter):
    global static_folder
    global files2remove
    global session
    outfilename = os.path.join(session_dir(session),"output_" + str(block_counter) + ".txt")
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

# HTML-sanitation
s = 4
esc_pairs = [[None] * 2 for y in range(s)]
esc_pairs[0] = ['\\','\\\\']
esc_pairs[1] = ['"','&quot;']
esc_pairs[2] = ['<','&lt;']
esc_pairs[3] = ['>','&gt;']
#esc_pairs[4] = ['\n',r'\n']

# Replace symbols that can distroy html test field contents.
def html_safe(command):
    for esc in esc_pairs:
        command = command.replace(esc[0],esc[1])
    return command


# Shutdown server
def shutdown():
    global files2remove
    global static_folder
    global session
    print "Shutting down"
    # Remove temporary files
    for file in files2remove:
        print "Delete "+file
        os.remove(file)
    shutil.rmtree(session_dir(session))
    pid = os.getpid()
    print "PID\t"+str(pid)
    ps = subprocess.check_output(["ps","ax",str(pid)])
    print ps
    subprocess.check_call(["kill",str(pid)])

bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)
