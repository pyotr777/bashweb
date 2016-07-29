#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.5alpha-2"

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
    script_number = 2

html_base = "index.html"
static_folder = web_folder+"/static"
default_block = web_folder+"/default.html"
block_counter = 0
WS_alive = False
pid = os.getpid()

try:
    session = os.environ["WEBINT_SESSION"]
except:
    session=""

command_list=[]
descript_list=[]
block_list=[]

# CONFIGURATION (workflow) initialisation
# Read command_list, descrition list and block list from tsv file "script.tsv"
with open(static_folder+"/config/script_"+str(script_number)+".tsv", 'r') as script:
    script = csv.reader(script, delimiter='\t')
    i = 0
    for row in script:
        print "row:" + str(row)
        block_list.append(row[0])
        if row[1] is None:
            print "Error: No command for block "+ str(i) + " in /config/script_"+str(script_number)+".tsv"
            shutdown()
        command_list.append(row[1])
        descript_list.append(row[2])
        i = i + 1


print "Webint v" + str(ver)
print "Web folder  : " + web_folder
print "Web page    : " + web_folder + "/" + html_base
print "Static folder: " + static_folder
print "Default block: " + default_block
print "Script:"
print command_list
print descript_list
print block_list


@webint.route('/')
def start():
    global session
    if bottle.request.query is None or bottle.request.query.session is None or len(bottle.request.query.session)<1:
        session = ''.join([random.choice(ascii_uppercase + digits) for n in xrange(8)])
        print "["+str(pid)+"]SESSION\t"+session
        return startSession()
    else:
        session = bottle.request.query.session
        print "["+str(pid)+"]NEW CONNECTION TO SESSION "+ session
        return attachSession(session)


def attachSession(session):
    global block_counter
    global static_folder
    sd = sessionDir(session)
    print "["+str(pid)+"]Attach to " + session
    # Create session dir if doesnt exist
    if not os.path.isdir(sd):
        print "+["+str(pid)+"]Creating session folder " + sd
        os.makedirs(sd)

    page = showIndex()
    print "["+str(pid)+"]Reading block files starting from 1"
    br_counter = 1
    result = getNext(br_counter, page)

    # Set block counter in browser
    print "["+str(pid)+"]BC\t" + str(block_counter)
    result = result + "\n<script>block_counter = "+str(block_counter)+";\n"
    result = result + "\nconsole.log(\"BC=\"+block_counter);</script>\n"
    return result


# Return session folder path
def sessionDir(session):
    return os.path.join(web_folder,"sessions",session)


# Try to read from saved output file
def readOutputFile(fname):
    write_flag = fname + "_W"
    # Wait if write flag file exists
    if os.path.isfile(write_flag):
        print "["+str(pid)+"] Write flag found: " + write_flag
        while os.path.isfile(write_flag):
            sleep(0.1)
    print "["+str(pid)+"] No write flag file"
    output_f = open(fname,'r')
    output = output_f.read()
    output = html_safe(output)
    output_f.close()
    return output


# Send start_session.html to browser
# which will reload to the same address now with ?session=... parameter.
def startSession():
    global block_counter
    global session
    block_counter = 0
    page = "start_session.html"
    print "["+str(pid)+"]Block counter reset to " + str(block_counter)
    file_name = web_folder+"/" + page
    print "["+str(pid)+"]Reading " + file_name
    start_file = open(file_name)
    block = start_file.read()
    start_file.close()
    # Replace default IDs with block unique IDs
    block = re.sub(r'SESSION',session,block)
    return block

# Return index.html
def showIndex():
    print "["+str(pid)+"]Reading base page "+ html_base
    index_filename = os.path.join(web_folder,html_base)
    index_f = open(index_filename)
    index = index_f.read()
    index_f.close()
    return index


# Load next block or return save block.
# Block number should be set in request parameters.
# If no number supplied use global block_counter
@webint.route('/next')
def next():
    print "["+str(pid)+"]Loading next block"
    # Check browser block counter
    if hasattr(bottle.request.query, 'counter') and bottle.request.query.counter is not None:
        b_counter = bottle.request.query.counter
        print "Have browser counter " + b_counter
        counter = int(b_counter)
        return getNext(counter,"")
    else:
        return getNext()


@webint.route('/exe', apply=[websocket])
def exe(ws):
    global env_vars
    global WS_alive
    global session

    print "["+str(pid)+"]Session="+session
    WS_alive = True
    print "WEB SOCKET\talive"
    msg = ws.receive()
    if msg is None or len(msg) == 0:
        print "Error: Null command in /exe"
        next_block=getNextNoCounter()
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    command,counter = parseCommand(msg)
    if counter is None or int(counter) is None:
        print "Error: no counter in message to WS: " + msg
        next_block=getNextNoCounter()
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return
    print "command\t" + command
    print "BC(browser)\t" + str(counter)
    if command.find("#SETVARS") == 0:
        print "setvars"
        # Got command with variables in it
        # Save vars into env_vars and return
        assignments = command.split(";")
        print assignments
        for assign in assignments:
            parse_vars(assign)
        # Create output file 
        outfilename = outputFileName(session,counter)
        output_file_handler = open(outfilename,'w')
        print "SERVARS output saved to " + outfilename
        output_file_handler.close()
        next_block=getNext(counter+1,"")
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    init_env = os.environ.copy()
    merged_env = init_env.copy()
    merged_env.update(env_vars)
    print "Exectuing "+command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged_env, bufsize=1, shell=True, executable="/bin/bash")
    handleProcessOutput(proc,ws,counter)  # Output save to file and sent to WS

    next_block=getNext(counter+1,"")
    ws.send("#NEXT"+next_block)
    print "Next block sent"
    WS_alive = False
    print "ws:==X==:ws"
    if next_block == "OK":
        shutdown()
    return
# End def exe(ws)


# Read output from step N of session S.
# Called by refresh script in browser.
# If process has finished (no running flag) return next block also.
@webint.route('/readoutput')
def readoutput():
    print "["+str(pid)+"]READ OUTPUT"
    # Read session ID
    if bottle.request.query is None or bottle.request.query.session is None or len(bottle.request.query.session)<1:
        print "No session parameter in request"
        return ""
    else:
        session = bottle.request.query.session
        print "have session "+ session
    # Read counter
    if bottle.request.query.block is None or len(bottle.request.query.block) < 1:
        print "Error: No block (counter) parameter in request"
        return ""
    else:
        counter = int(bottle.request.query.block)
        print "have counter "+ bottle.request.query.block

    output_fname = outputFileName(session, counter)
    print "Looking for output "+ output_fname
    out = ""
    if os.path.isfile(output_fname):
        #print "Found "+output_fname
        out = readOutputFile(output_fname)
        # If process is in progress, attache refresh script
        run_flag = output_fname + "_"
        if os.path.isfile(run_flag):
            print "Run flag found: " + run_flag
            return out
        print "No run flag"

    # Script to sopt continous reloading
    stop_script='''<script>
        active_refresh = 0;
        console.log("Acitve refresh var="+active_refresh);
        console.log("Load next="+load_next);
        if (load_next) {
            console.log("Loading next block '''+session+" "+str(counter+1)+'''");
            $("body").append($("<div>").load("/next?session='''+session+"&counter="+str(counter+1)+'''"));
            load_next = 0; // prevent multiple loads of same block
        }
        </script>'''
    out = out + stop_script
    return out
# End def readoutput()


# Add / replace parts of XML file
@webint.post('/xml/edit/<command_n>')
def edit_xml(command_n):
    print "["+str(pid)+"]edit_xml called with " + command_n
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    # Get file path
    filepath, counter = parseCommand(command_n)
    if counter is None or int(counter) is None:
        print "Error: no counter in command to /xml/edit: " + msg
        print >> err, "Error: no counter in command to /xml/edit"
        stdout = out.getvalue()
        stderr = err.getvalue()
        out.close()
        err.close()
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter+1)})
    print "["+str(pid)+"]Editing "+filepath
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
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter+1)})

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
            return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter+1)})

        except:
            print >> err, sys.exc_info()
            print >> err, "Not found: " + key
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter+1)})

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
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter+1)})

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
        return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter+1)})

    new_xml = frd.read()
    frd.close()
    print >> out, html_safe(new_xml)

    # Open output file
    outfilename = os.path.join(sessionDir(session),"output_" + str(counter) + ".txt")
    output_file_handler = openOutputFile(outfilename)
    print >> output_file_handler, new_xml,
    closeOutputFile(output_file_handler)

    # Return stdout and stderr
    stdout = out.getvalue()
    print "Stdout:" + stdout
    stderr = err.getvalue()
    out.close()
    err.close()

    return json.dumps({'stdout':stdout, 'stderr':stderr, 'next': getNext(counter + 1)})
# End def edit_xml(command_n)


@webint.route('/<filename>')
def show_html(filename):
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)


@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    #print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)



# Return output file name
def blockFileName(session,counter):
    return os.path.join(sessionDir(session),"block_" + str(counter) + ".html")

# Return output file name
def outputFileName(session,counter):
    return os.path.join(sessionDir(session),"output_" + str(counter) + ".txt")


# Process execution
# Save output in output_NNN.txt file, send to web socket and to server stdout.
def handleProcessOutput(proc, ws, counter):
    global WS_alive
    global session
    # Output file name
    outfilename = os.path.join(sessionDir(session),"output_" + str(counter) + ".txt")
    # Running flag file
    # Indicates that this step is not finished. Used in session fastforwarding.
    RFF=outfilename+"_"
    print "Run flag file " + RFF
    RFF_h = open(RFF,'w')
    RFF_h.close()
    # Display lines in batches
    # After batch_size lines make a short pause to enable multiple requests processing
    batch_size = 10  # Number of lines to read before pause.
    sleep_time = 0.1 # Pause length in seconds.
    line_counter = 0
    # Loop with running process output
    for line in iter(proc.stdout.readline, b''):
        # Open file for writing
        output_file_handler = openOutputFile(outfilename)
        if WS_alive:
            try:
                ws.send(html_safe(line))
            except WebSocketError as ex:
                print "Web socket died."
                WS_alive = False;
        # print line,
        print >> output_file_handler, line,
        parse_vars(line)
        line_counter+=1
        if line_counter >= batch_size:
            closeOutputFile(output_file_handler)
            sleep(sleep_time)
            line_counter = 0
    if os.path.isfile(outfilename):
        closeOutputFile(output_file_handler)
    print "["+str(pid)+"]Finished"
    proc.wait()
    # Remove RFF
    print "Delete "+RFF
    os.remove(RFF)


# Return next block useing server-side BC
def getNextNoCounter():
    global block_counter
    return(getNext(block_counter + 1),"")


# Return block with number 'counter' and append it to 'result'.
# If block is saved (in session folder) use saved version and 
# also append saved output if exists.
# ! This should be the only function that sets (alters) block_counter.
def getNext(counter=None, result=""):
    global block_counter
    global block_list
    global static_folder
    global session
    # Flag if we in FastForward mode and need next block
    read_next_block = False
    if counter is None:
        print "["+str(pid)+"] Error: no counter in getNext"
        block_counter += 1
        counter = block_counter
        print "BC set to " + str(counter)
    else:
        counter = int(counter)
        if counter > block_counter:
            print "block_counter shoud be equal to counter\t"+str(block_counter)+"\t" + str(counter)
            block_counter = counter

    print "["+str(pid)+"]Get next ("+str(counter)+")"
    print "BC\t" + str(block_counter)
    if counter > len(block_list):
        print "No more commands"
        return "OK"

    # Check if block counter is saved
    block_fname = blockFileName(session, counter)
    # USe saved block
    if os.path.isfile(block_fname):
        print "["+str(pid)+"]Found saved block " + block_fname
        block_f = open(block_fname,'r')
        block = block_f.read()
        block_f.close()
        # Append saved block contents to result
        result = result + block
        # Check output file
        output_fname = string.replace(block_fname,'block_','output_')
        output_fname = string.replace(output_fname,'.html','.txt')
        if os.path.isfile(output_fname):
            read_next_block = True  # Get next block if output is saved fully (no run flag)
            print "-["+str(pid)+"]Reading ouput "+ output_fname
            output = "<div class=\"displayblock\" id="+session+"_"+str(counter)+">" + readOutputFile(output_fname) + "</div>\n"
            # Check if this step is in progress (subprocess hasn't finished)
            # If process is in progress, attach refresh script
            run_flag = output_fname + "_"
            if os.path.isfile(run_flag):
                print "-["+str(pid)+"]Run flag found: " + run_flag
                read_next_block = False
                refresh_script = RefreshScript(session, str(counter))
                print "Attaching refresh script to putput"
                output = output + refresh_script
            # Append output to result
            result = result + output

        # Need next block
        # ! INDENTION SHOULD BE SAME AS if os.path.isfile(output_fname):
        if read_next_block:
            result = getNext(counter+1,result)

    # Use raw block
    else:
        block_f = web_folder+"/" + block_list[counter-1]
        print "["+str(pid)+"]Use raw block " + block_f
        div_block_h = open(block_f)
        div = div_block_h.read()
        div_block_h.close()
        # Replace default IDs with block unique IDs
        div = re.sub(r'NNN',str(counter),div)
        # And command
        div = re.sub(r'COMMAND',str(counter),div)
        # Discription
        div = re.sub(r'DISCRIPTION',descript_list[counter-1],div)
        # Save block to file blockNNN.html
        outfilename = os.path.join(sessionDir(session),"block_" + str(counter) + ".html")
        if not os.path.isfile(outfilename):
            print "Write to " + outfilename
            out_block_file = open(outfilename, 'w')
            out_block_file.write(div)
            out_block_file.write("\n")
            out_block_file.close()
        # Append to result
        result = result + div
    return result
# End of getNext(counter=None, result="")


# Rreturn javascript for refreshing current div
def RefreshScript(session, counter):
    script = '''
        <script>
        var active_refresh = 1; // Autoreload div contents with timeout.
        var load_next = 1;   // Load next block when output loaded to the end.
        function refreshDiv() {
            if (active_refresh) {
                console.log("Refresh script is running with active_refres=" + active_refresh)
                console.log("Requesting /readoutput?session='''+session+"&block="+counter+'''");
                $("#'''+session+"_"+counter+'''").load("/readoutput?session='''+session+"&block=" + counter + '''");
                $("#'''+session+"_"+counter+'''").animate({ scrollTop: $("'''+session+"_" + counter +'''").prop("scrollHeight")}, 100);
                setTimeout( refreshDiv, 1000);
            }
            console.log("Refreshing in 2s: "+active_refresh)
        };
        if (active_refresh) {
            setTimeout( refreshDiv, 2000);
        }
        </script>'''
    return script


# Open output file
def openOutputFile(outfilename):
    # Flag file indicationg that file is in use.
    flag_filename = outfilename+"_W"
    FF_h = open(flag_filename,'w')
    FF_h.close()
    output_file = open(outfilename, 'a')
    #print "Write output to " + outfilename
    return output_file

def closeOutputFile(f_handle):
    fname = f_handle.name
    #print "Closing " + fname
    f_handle.close()
    # Remove writing flag file
    flag_filename = fname + "_W"
    if os.path.isfile(flag_filename):
        #print "Delete " + flag_filename
        os.remove(flag_filename)



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
        counter = int(parts[0])
        command = command_list[counter - 1] + ";" + ";".join(parts[1:])
    else:
        counter = int(msg)
        command = command_list[counter - 1]
    return command,counter

# HTML-sanitation
s = 8
esc_pairs = [[None] * 2 for y in range(s)]
# Replacemnt pairs
# ! Order is important !
esc_pairs[0] = ['\\','\\\\']
esc_pairs[1] = ['&','&amp;']
esc_pairs[2] = ['"','&quot;']
esc_pairs[3] = ['<','&lt;']
esc_pairs[4] = ['>','&gt;']
esc_pairs[5] = ['\'','&#039;']
esc_pairs[6] = ["[38;5;70m", "<span style=\"color:#32b50a;\">"]
esc_pairs[7] = ["[m", "</span>"]

# Replace symbols that can distroy html test field contents.
def html_safe(data):
    for esc in esc_pairs:
        data = data.replace(esc[0],esc[1])
    return data


# Shutdown server
def shutdown():
    global static_folder
    global session
    print "Shutting down"
    # Remove session files
    shutil.rmtree(sessionDir(session))
    pid = os.getpid()
    print "PID\t"+str(pid)
    ps = subprocess.check_output(["ps","ax",str(pid)])
    print ps
    subprocess.check_call(["kill",str(pid)])

bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)
