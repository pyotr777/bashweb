#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.4alpha-2"

import bottle
import subprocess
import shlex
import re
import string
import urllib
import os
import stat
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

# Template file names
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
        print "["+str(pid)+"]SESSION\t"+session
        return start_session()
    else:
        session = bottle.request.query.session
        print "["+str(pid)+"]NEW CONNECTION TO SESSION "+ session
        return attach_session(session)

def attach_session(session):
    global block_counter
    global static_folder
    sd = session_dir(session)
    print "-["+str(pid)+"]Attach to " + session
    if not os.path.isdir(sd):
        print "-["+str(pid)+"]Creating session folder " + sd
        os.makedirs(sd)
        return show_index()
    else:
        page = show_index()
        print "-["+str(pid)+"]Reading block files"
        br_counter = 1
        last_block = False
        block_fname = blockFileName(session, br_counter)
        if os.path.isfile(block_fname):
            # Deactivate index.html (prevent loading next block again)
            page = re.sub(r'var\s*active\s*=\s*1[;]*',r'var active = 0;', page)
            # Deactivate only if there is at least one block saved
        while (os.path.isfile(block_fname) and not last_block):
            print "-["+str(pid)+"]Reading block " + block_fname
            block_f = open(block_fname,'r')
            block = block_f.read()
            page = page + block
            block_f.close()
            # Read output
            output_fname = string.replace(block_fname,'block_','output_')
            output_fname = string.replace(output_fname,'.html','.txt')
            if os.path.isfile(output_fname):
                print "-["+str(pid)+"]Reading ouput "+output_fname
                page = page + "<div class=\"displayblock\" id="+session+"_"+str(br_counter)+">" + readOutputFile(output_fname) + "</div>\n"
                # Check if this step is in progress (subprocess hasn't finished)
                # If process is in progress, attache refresh script
                run_flag = output_fname + "_"
                if os.path.isfile(run_flag):
                    print "-["+str(pid)+"]Run flag found: " + run_flag
                    refresh_script = RefreshScript(session, str(br_counter))
                    print refresh_script
                    page = page + refresh_script
                    last_block = True
                else:
                    br_counter += 1
                    block_fname = blockFileName(session, br_counter)
                    print "-["+str(pid)+"]Loop ends with " + block_fname
            else:
                print "-["+str(pid)+"]No output file"
                br_counter += 1
                block_fname = blockFileName(session, br_counter)

        # Synchronise counters for this webint instance and browser to number of blocks in session folder
        if br_counter > block_counter:
            block_counter = br_counter
            print "-["+str(pid)+"]BC updated to " + str(block_counter)
        print "-["+str(pid)+"]Set block_counter in browser to " + str(br_counter)        
        page = page + "\n<script>block_counter = "+str(br_counter)+";\n"
        page = page + "\nconsole.log(\"BC=\"+block_counter);</script>\n"
        return page


# Return session folder path
def session_dir(session):
    return os.path.join(web_folder,"sessions",session)

# Try to read from saved output file
def readOutputFile(fname):
    write_flag = fname + "_W"
    # Wait if write flag file exists
    if os.path.isfile(write_flag):
        print "["+str(pid)+"] Write flag file found"
        while os.path.isfile(write_flag):
            sleep(0.1)
    print "["+str(pid)+"] No write flag file"
    output_f = open(fname,'r')
    output = output_f.read()
    output = html_safe(output)
    output_f.close()
    return output


# Rreturn javascript for refreshing current div
def RefreshScript(session, counter):
    script = '''
        <script>
        var active_refresh = 1; // Autoreload div contents with timeout.
        var load_next = 1;   // Load next block when output loaded to the end.
        function refreshDiv() {
            if (active_refresh) {
                console.log("Requesting /readoutput?session='''+session+"&block="+counter+'''");
                $("#'''+session+"_"+counter+'''").load("/readoutput?session='''+session+"&block=" + counter + '''");
                $("'''+session+"_"+ counter+'''").animate({ scrollTop: $("'''+session+"_" + counter +'''").prop("scrollHeight")}, 1000);
                setTimeout( refreshDiv, 1000);
            }
            console.log("Refreshing in 2s: "+active_refresh)
        };
        if (active_refresh) {
            setTimeout( refreshDiv, 2000);
        }
        </script>'''
    return script

def start_session():
    global block_counter
    global session
    block_counter = 0
    page = "["+str(pid)+"]start_session.html"
    print "["+str(pid)+"]Block counter reset to " + str(block_counter)
    file_name = web_folder+"/" + page
    print "["+str(pid)+"]Reading " + file_name
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
    print "["+str(pid)+"]Reading base page "+ html_base
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


# Load next block or return save block.
# Block number should be set in request parameters.
# If no number supplied use global block_counter
@webint.route('/next')
def next():
    global block_counter
    global pid
    print "["+str(pid)+"]Loading next block " + str(block_counter)
    # Check browser block counter
    if hasattr(bottle.request.query, 'counter') and bottle.request.query.counter is not None:
        b_counter = bottle.request.query.counter
        print "have browser counter " + b_counter
        br_counter = int(b_counter)
        if block_counter < br_counter:
            block_counter = br_counter
    else:
        print "Counter not in query"
        br_counter = block_counter
            
    # Check block file
    block_fname = blockFileName(session, br_counter)
    if os.path.isfile(block_fname):
        print "-Reading block file " + block_fname
        block_f = open(block_fname,'r')
        block = block_f.read()
        block_f.close()
        return block
    else:
        print "No saved block found"    
    return getNext(br_counter)

@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    #print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)

@webint.route('/exe', apply=[websocket])
def exe(ws):
    global env_vars
    global block_counter
    global WS_alive
    global session
    execute_command = True
    print "["+str(pid)+"]Session="+session
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

    command,counter = parseCommand(msg)
    print "Have command " + command
    print "BC(browser):\t" + str(counter)
    br_counter = counter + 1
    if command.find("#SETVARS") == 0:
        print "setvars"
        # Got command with variables in it
        # Save vars into env_vars and return
        assignments = command.split(";")
        print assignments
        for assign in assignments:
            parse_vars(assign)
        # Create output file 
        # Must be called before getNext to use correct block_counter
        outfilename = outputFileName(session,block_counter)
        output_file_handler = open(outfilename,'w')
        print "SERVARS output saved to " + outfilename
        output_file_handler.close()
        next_block=getNext(br_counter)
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    if execute_command:
        init_env = os.environ.copy()
        merged_env = init_env.copy()
        merged_env.update(env_vars)
        print "Exectuing "+command
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged_env, bufsize=1, shell=True, executable="/bin/bash")
        handleProcessOutput(proc,ws,block_counter)

    next_block=getNext(br_counter)
    ws.send("#NEXT"+next_block)
    print "Next block sent"
    WS_alive = False
    print "ws:==X==:ws"
    if next_block == "OK":
        shutdown()
    return


# Read output from step N of session S
# If process has finished (no running flag) return next block also.
@webint.route('/readoutput')
def readoutput():
    global block_counter
    global session    
    print "["+str(pid)+"]READ OUTPUT"
    if bottle.request.query is None or bottle.request.query.session is None or len(bottle.request.query.session)<1:
        print "No session parameter in request"
        return ""
    else:
        session = bottle.request.query.session
        print "have session "+ session

    # SEt block counter br_counter
    br_counter = block_counter # default value
    if bottle.request.query.block is None or len(bottle.request.query.block)<1:
        print "Error: No block (counter) parameter in request"
        return ""
    else:
        br_counter = int(bottle.request.query.block)
        print "have block counter "+ bottle.request.query.block

    output_fname = outputFileName(session,br_counter)
    print "Looking for output "+ output_fname
    out = "No file found: " + output_fname
    if os.path.isfile(output_fname):
        #print "Found "+output_fname
        out = readOutputFile(output_fname)
        # If process is in progress, attache refresh script
        run_flag = output_fname + "_"
        if os.path.isfile(run_flag):
            print "Run flag found: " + run_flag
            return out
    print "No run flag or output block"
    br_counter += 1 
    stop_script='''
        <script>
        active_refresh = 0;
        console.log("Acitve refresh var="+active_refresh);
        console.log("Load next="+load_next);
        if (load_next) {
            console.log("Loading next block '''+session+" "+str(br_counter)+'''");
            $("body").append($("<div>").load("/next?session='''+session+"&counter="+str(br_counter)+'''"));
            load_next = 0; // prevent multiple loads of same block
        }
        </script>
        '''
    out = out + stop_script       
    return out


# Return output file name
def blockFileName(session,counter):
    return os.path.join(session_dir(session),"block_" + str(counter) + ".html")

# Return output file name
def outputFileName(session,counter):
    return os.path.join(session_dir(session),"output_" + str(counter) + ".txt")


# Process execution
# Save output in output_NNN.txt file, send to web socket and to server stdout.
def handleProcessOutput(proc, ws, counter):
    global WS_alive
    global session
    # Output file name
    outfilename = os.path.join(session_dir(session),"output_" + str(block_counter) + ".txt")
    # Running flag file
    # Indicates that this step is not finished. Used in session fastforwarding.
    RFF=outfilename+"_"
    print "Run flag file " + RFF
    RFF_h = open(RFF,'w')
    RFF_h.close()
    # Display lines in batches
    # After batch_size lines make a short pause to enable multiple requests processing
    batch_size = 10
    line_counter = 0
    # Loop with running process output
    for line in iter(proc.stdout.readline, b''):
        # Open file for writing
        output_file_handler = openOutputFile(outfilename)
        if WS_alive:
            try:
                ws.send(line)
            except WebSocketError as ex:
                print "Web socket died."
                WS_alive = False;
        # print line,
        print >> output_file_handler, line,
        parse_vars(line)
        line_counter+=1
        if line_counter >= batch_size:
            closeOutputFile(output_file_handler)
            sleep(0.1)
            line_counter = 0
    if os.path.isfile(outfilename):
        closeOutputFile(output_file_handler)
    print "["+str(pid)+"]Finished"
    proc.wait()
    # Remove RFF
    print "Delete "+RFF
    os.remove(RFF)


# Add / replace parts of XML file
@webint.post('/xml/edit/<command_n>')
def edit_xml(command_n):
    next_block=getNext()
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    # Get file path
    filepath,counter = parseCommand(command_n)
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
    outfilename = os.path.join(session_dir(session),"output_" + str(block_counter-1) + ".txt")
    output_file_handler = openOutputFile(outfilename)  # Decrement beacuse getNext() called before this point
    print >> output_file_handler, new_xml,
    closeOutputFile(output_file_handler)

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
    global session
    if counter is None:
        print "["+str(pid)+"] no counter in getNext"
        block_counter += 1
        counter = block_counter
        print "counter set to " + str(counter)
    else:
        counter = int(counter)
        if counter > block_counter:            
            print "block_counter shoud be equal to counter\t"+str(block_counter)+"\t" + str(counter)
            block_counter = counter

    print "["+str(pid)+"]Get next ("+str(counter)+")"
    print "BC\t" + str(block_counter)
    if counter > len(command_list):
        print "No more commands"
        os.remove
        return "OK"
    if counter <= len(block_list):
        block = web_folder+"/" + block_list[counter-1]
    print "Use " + block
    # Default DIV block transformations
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
        out_block_file.write(div)
        out_block_file.write("\n")
        out_block_file.close()
    return div


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
    global static_folder
    global session
    print "Shutting down"
    # Remove session files
    shutil.rmtree(session_dir(session))
    pid = os.getpid()
    print "PID\t"+str(pid)
    ps = subprocess.check_output(["ps","ax",str(pid)])
    print ps
    subprocess.check_call(["kill",str(pid)])

bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)
