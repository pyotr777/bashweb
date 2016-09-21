#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CHITEC, Stair Lab

ver = "0.12beta-1"

import bottle
import subprocess
import re
import string
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
from geventwebsocket.websocket import WebSocketError
from ansi2html import Ansi2HTMLConverter
import yaml
import pprint
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

html_base = "index.html"
static_folder = web_folder+"/static"
blocks_folder = web_folder+"/blocks"
config_folder = web_folder+"/config"
default_block = web_folder+"/default.html"
WS_alive = []  # List of sessions with open WS connections
pid = os.getpid()
sleep_time = 0.01 # Pause length in seconds.


# CONFIGURATION (workflow) initialisation
# Read command_list, descrition list and block list from tsv file "script.tsv"
with open(config_folder+"/script_"+str(script_number)+".yml", 'r') as script:
    config = yaml.load(script)


print "Webint v" + str(ver)
print "Web folder  : " + web_folder
print "Web page    : " + web_folder + "/" + html_base
print "Static folder: " + static_folder
print "Default block: " + default_block
print "Script:"
print yaml.dump(config)


@webint.route('/')
def start():
    session = getSessionID(bottle.request)
    if  session == "":
        session = ''.join([random.choice(ascii_uppercase + digits) for n in xrange(8)])
        print "["+str(pid)+"]SESSION\t"+session
        return startSession(session)
    else:
        print "["+str(pid)+"]NEW CONNECTION TO SESSION "+ session
        return attachSession(session)


def getSessionID(request):
    # Read session ID
    if request.query is None or request.query.session is None or len(request.query.session)<1:
        print "No session parameter in request"
        return ""
    else:
        return request.query.session


def attachSession(session):
    global static_folder
    sd = sessionDir(session)
    print "["+str(pid)+"]Attach to " + session
    # Create session dir if doesnt exist
    if not os.path.isdir(sd):
        print "+["+str(pid)+"]Creating session folder " + sd
        os.makedirs(sd)

    page = showIndex()
    print "["+str(pid)+"]Reading block files starting from 1"
    counter = 1
    counter, result = getNext(counter, page, session=session)

    # Set block counter in browser
    print "["+str(pid)+"]BC\t" + str(counter)
    result = result + "\n<script>block_counter = "+str(counter)+";\n"
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
    print "No write flag file"
    output_f = open(fname,'r')
    output = output_f.read()
    output = html_safe(output.decode('utf-8'))
    # .decode(utf-8) to fix UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2 in position 954875: ordinal not in range(128) error.
    output_f.close()
    return output


# Send start_session.html to browser
# which will reload to the same address now with ?session=... parameter.
def startSession(session):
    global env_vars
    # Init env_vars for this session
    env_vars[session] = dict()
    page = "start_session.html"
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
# Block number must be set in request parameters.
@webint.route('/next')
def next():
    print "["+str(pid)+"]Loading next block"
    result = ""
    session = getSessionID(bottle.request)
    # If no session ID, it means start over from clean page. Need to return index.html.
    if  session == "":
        page = showIndex()
        print "["+str(pid)+"]Reading block files starting from 1"
        counter = 1
        result = page + "\n<script>block_counter = "+str(counter)+";\n"
        result = result + "\nconsole.log(\"BC=\"+block_counter);</script>\n"

    # Check browser block counter
    if hasattr(bottle.request.query, 'counter') and bottle.request.query.counter is not None:
        b_counter = bottle.request.query.counter
        print "Have browser counter " + b_counter
        counter = int(b_counter)
        print "Call getNext with (" + b_counter+", force_next=" + str(True)+ ")"
        counter, next_block = getNext(counter, result, session,  force_next = True)
        #TODO Return next_block with counter in JSON format
        return next_block
    else:
        counter, next_block = getNext(result=result, session=session, force_next = True)
        #TODO Return next_block with counter in JSON format
        return next_block


@webint.route('/exe', apply=[websocket])
def exe(ws):
    global WS_alive
    session = getSessionID(bottle.request)
    if session != "":
        print "["+str(pid)+"]Session="+session
        session_name=session
    else:
        print "["+str(pid)+"]No session"
        session_name="nosession"
      
    if session_name not in WS_alive:
        WS_alive.append(session_name)
    print "WEB SOCKET for "+session_name+" open"
    msg = ws.receive()
    if msg is None or len(msg) == 0:
        print "Error: Null command in /exe"
        counter, next_block=getNext(session=session)
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    parsed_yaml = yaml.safe_load(msg)
    print "Received message "+yaml.dump(parsed_yaml)
    counter = int(parsed_yaml["command"])
    print str(counter) +"/" + str(len(config))
    if counter is None or int(counter) is None:
        print "Error: no counter in message to WS: " + msg
        counter, next_block=getNext(session=session)
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return
    if counter > len(config):
        print "No more commands"
        # Shutdown if counter > block list length and previous command was STOP
        if prev_scenario == "STOP":
            shutdown()
        if counter > len(config):
            # Jumped to nonexisting command, shutdown server.
            shutdown()

    command = config[configCounter(counter)]["command"]
    print "command\t" + command
    if command == "#SETVARS":
        print "setvars"
        # Got command with variables in it
        # Save vars into env_vars and return
        if parsed_yaml["args"] is not None:
            print "args=" + str(parsed_yaml["args"])
            print "Allowed vars:"
            print config[configCounter(counter)]["allowed_vars"]
        parseVars(parsed_yaml["args"],config[configCounter(counter)]["allowed_vars"],session)
        # Create output file
        outfilename = outputFileName(session,counter)
        output_file_handler = open(outfilename,'w')
        print "SETVARS output saved to " + outfilename
        output_file_handler.close()
        counter, next_block=getNext(counter+1, session=session)
        ws.send("#NEXT"+next_block)
        print "Next block sent"
        return

    if command == "#SHUTDOWN":
        print "Got shutdown command."
        shutdown(session)
        return

    init_env = os.environ.copy()
    merged_env = init_env.copy()
    if session != "":
        merged_env.update(getEnvVars(session))
    # Substitute arguments in command
    if "args" in parsed_yaml and parsed_yaml["args"] is not None:
        print "[] Has arguments: " + str(parsed_yaml["args"])
        command = substituteArgs(command, parsed_yaml["args"])
    print "Exectuing "+command
    #print "Environment " + str(merged_env)
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged_env, bufsize=1, shell=True, executable="/bin/bash")
    handleProcessOutput(proc,ws,counter,session)  # Output save to file and sent to WS

    counter, next_block=getNext(counter+1, session=session)
    ws.send("#NEXT"+next_block)
    print "Next block sent"
    WS_alive.remove(session_name)
    return
# End def exe(ws)


# Return dictionary with environment variables for given session.
# Use top-level dictionary "nosession" if session is not given.
def getEnvVars(session=""):
    global env_vars

    if session == "":
        dict_name = "nosession"
    else:
        dict_name = session
        if dict_name not in env_vars:
            env_vars[session] = dict()
    return env_vars[dict_name]


# Read output from step N of session S.
# Called by refresh script in browser.
# If process has finished (no running flag) return next block also.
@webint.route('/readoutput')
def readoutput():
    print "["+str(pid)+"]READ OUTPUT"
    # Read session ID
    session = getSessionID(bottle.request)
    if session == "":
        print "No session parameter in request"
        return ""
    else:
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
        # html_safe applied inside readOutputFile function
        out = readOutputFile(output_fname)
        # If process is in progress, do not attach stop_script
        run_flag = output_fname + "_"
        if os.path.isfile(run_flag):
            print "Run flag found: " + run_flag
            return out
        print "No run flag"

    # Script to stop continous reloading
    stop_script='''<script>
        active_refresh = 0;
        console.log("Acitve refresh var="+active_refresh);
        console.log("Load next="+load_next);
        if (load_next) {
            console.log("Loading next block '''+session+" "+str(counter+1)+'''");
            $("body").append($("<div>").load("/next?session='''+session+'''&counter='''+str(counter+1)+'''"));
            load_next = 0; // prevent multiple loads of same block
        }
        </script>'''
    out = out + stop_script
    return out
# End def readoutput()


# Add / replace parts of XML file
@webint.post('/xml/edit/<command_n>')
def edit_xml(command_n):
    global config

    print "["+str(pid)+"]edit_xml called with " + command_n
    session = getSessionID(bottle.request)
    if session != "":
        print "Session="+session
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    # Get file path

    counter = int(command_n)
    if counter is None or int(counter) is None:
        return returnError(out, err, session, "Error: no counter in command to /xml/edit: " + command_n, counter)
    
    command = config[configCounter(counter)]["command"]
    print "command\t" + command
        
    if config[configCounter(counter)]["filepath"] is None  or len(config[configCounter(counter)]["filepath"]) < 1:
        return returnError(out, err, session,"Filepath for command "+str(counter)+" not set in configuration script.", counter)
    filepath = config[configCounter(counter)]["filepath"]

    print "["+str(pid)+"]Editing "+filepath
    # Open file
    if filepath.find("/") != 0:
        filepath = web_folder+"/" +filepath
    # Read file
    try:
        f = etree.parse(filepath)
    except IOError as ex:
        return returnError(out, err, session,"Error reading file " + filepath, counter)

    keys = bottle.request.forms.keys()
    for key in keys:
        val = bottle.request.forms.get(key)
        try:
            node = f.xpath(key)
            if type(node[0]) is etree._Element:
                # XML node element
                node[0].text = val
            elif type(node[0]) is etree._ElementStringResult:
                # XML tag element
                parent = node[0].getparent()
                # Get tag name
                parts = key.split("@")
                tagname = parts[len(parts)-1]
                parent.set(tagname, val)
        except etree.XPathEvalError:
            print >> err, sys.exc_info()
            return returnError(out, err, session, "Wrong path syntax: " + key, counter)
        except:
            print >> err, sys.exc_info()
            return returnError(out, err, session, "Not found: " + key, counter)

    print etree.tostring(f)
    # Save to file
    try:
        fwrt = open(filepath,'w')
    except IOError as ex:
        return returnError(out, err, session, "Error writing to file " + filepath, counter)

    print >> fwrt, etree.tostring(f)
    fwrt.close()
    print "Wrote XML to " + filepath
    try:
        frd = open(filepath,'r')
    except IOError as ex:
        return returnError(out, err, session, "Error reading file " + filepath, counter)

    new_xml = frd.read()
    frd.close()
    print >> out, new_xml,

    if session != "":
        # Open output file
        outfilename = os.path.join(sessionDir(session),"output_" + str(counter) + ".txt")
        print "Writing output to file " + outfilename
        output_file_handler = openOutputFile(outfilename)
        print >> output_file_handler, new_xml,
        closeOutputFile(output_file_handler)

    next_counter, next_block = getNext(counter+1, session=session)
    # Return stdout and stderr
    stdout = out.getvalue()
    print "Stdout:" + stdout
    stderr = err.getvalue()
    out.close()
    err.close()

    return json.dumps({'stdout':html_safe(stdout), 'stderr':html_safe(stderr), 'next': next_block, 'counter': counter})
# End def edit_xml(command_n)


@webint.route('/<filename>')
def show_html(filename):
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)


@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    #print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)


# Substitute $ARG placeholders in command with argument values
def substituteArgs(command, args):
    # Loop through parsed object attributes
    for key, value in args.iteritems():
            key = str(key)  # Convert from Unicode
            value = str(value)
            print "key:"+key + " val:"+ str(value)
            command = command.replace("$"+key,value)
    return command

# Return output file name
def blockFileName(session,counter):
    return os.path.join(sessionDir(session),"block_" + str(counter) + ".html")

# Return output file name
def outputFileName(session,counter):
    return os.path.join(sessionDir(session),"output_" + str(counter) + ".txt")


# Process execution
# Save output in output_NNN.txt file, send to web socket and to server stdout.
def handleProcessOutput(proc, ws, counter,session=""):
    global WS_alive
    global sleep_time

    if session != "":
        session_name = session
        # Output file name
        outfilename = os.path.join(sessionDir(session),"output_" + str(counter) + ".txt")
        # Running flag file
        # Indicates that this step is not finished. Used in session fastforwarding.
        RFF=outfilename+"_"
        print "Run flag file " + RFF
        RFF_h = open(RFF,'w')
        RFF_h.close()
    else:
        session_name = "nosession"

    # Display lines in batches
    # After batch_size lines make a short pause to enable multiple requests processing
    batch_size = 20  # Number of lines to read before pause.
    line_counter = 0
    # Loop with running process output
    for line in iter(proc.stdout.readline, b''):
        if session != "":
            # Open file for writing
            output_file_handler = openOutputFile(outfilename)
        if session_name in WS_alive:
            try:
                ws.send(html_safe(line))
            except WebSocketError as ex:
                print "Web socket died."
                WS_alive.remove(session_name)
        else :
            print session_name + " not in " + str(WS_alive)
        print line,
        if session != "":
            print >> output_file_handler, line,
        line_counter+=1
        if line_counter >= batch_size:
            if session != "":
                closeOutputFile(output_file_handler)
            sleep(sleep_time)
            line_counter = 0
    if session != "" and os.path.isfile(outfilename):
        closeOutputFile(output_file_handler)
    print "["+str(pid)+"]Finished"
    proc.wait()
    if session != "":
        # Remove RFF
        print "Delete "+RFF
        os.remove(RFF)


# Return JSON with error message for sending to browser
def returnError(out, err, session, msg, counter):
    print  >> err, msg
    stdout = out.getvalue()
    stderr = err.getvalue()
    out.close()
    err.close()
    counter, next_block = getNext(counter, session=session)
    return json.dumps({'stdout':html_safe(stdout), 'stderr':html_safe(stderr), 'next': next_block, 'counter': counter})


# Return block with number 'counter' and append it to 'result'.
# If block is saved (in session folder) use saved version and
# also append saved output if exists.
def getNext(counter=None, result="", session="", force_next=False):
    global config
    
    print "["+str(pid)+"]Get next ("+str(counter)+"), force " + str(force_next)
    # Flag if we in FastForward mode and need next block
    read_next_block = False
    if counter is None:
        print >> sys.stderr, "["+str(pid)+"] Error: no counter in getNext"
        return 0,""

    scenario = "NEXT"
    prev_scenario = "NEXT"
    print "Configuration has " + str(len(config)) + " commands."

    if counter > 1 and counter-1 < len(config):
        prev_scenario =  config[configCounter(counter-1)]["scenario"] #scenario_list[counter-2]

    print "session="+session
    print "Previous scenario command was " + str(prev_scenario)
    
    if prev_scenario == "STOP":
        print "Stop command"
        if not force_next:
            return counter, result
        else:
            print "Forced to next block"

    if counter >= len(config):
        print "No more commands"
        # Shutdown if counter > block list length and previous command was STOP
        if prev_scenario == "STOP":
            shutdown()
        if counter > len(config):
            # Jumped to nonexisting command, shutdown server.
            shutdown()

    # Check next scenario
    scenario = config[configCounter(counter)]["scenario"]
    print "This scenario command is " + str(scenario)
    if prev_scenario == "PART" and not force_next:
        # Do not load next block if for PART command came not from /next (with force_next)
        print "Suppose block " + str(counter) + " was already loaded into browser."
        return counter, result

    use_saved_block = False
    if session != "":
        # Check if block counter is saved
        block_fname = blockFileName(session, counter)
        # USe saved block
        if os.path.isfile(block_fname):
            print "["+str(pid)+"]Found saved block " + block_fname
            use_saved_block = True
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
                output = "<div class=displayblock id=out" + str(counter) + ">" + readOutputFile(output_fname) + "</div>\n"
                # Check if this step is in progress (subprocess hasn't finished)
                # If process is in progress, attach refresh script
                run_flag = output_fname + "_"
                if os.path.isfile(run_flag):
                    print "-["+str(pid)+"]Run flag found: " + run_flag
                    read_next_block = False
                    refresh_script = RefreshScript(session, str(counter))
                    print "Attaching refresh script to output"
                    output = output + refresh_script
                # Append output to result
                result = result + output

            # Need next block
            # ! INDENTION SHOULD BE SAME AS if os.path.isfile(output_fname):
            if read_next_block:
                counter, result = getNext(counter+1, result, session, True)

    if not use_saved_block:
        # Use raw block
        block_f = blocks_folder+"/" + config[configCounter(counter)]["html"]
        print "["+str(pid)+"]Use raw block " + block_f
        div_block_h = open(block_f)
        div = div_block_h.read()
        div_block_h.close()
        # Replace default IDs with block unique IDs
        div = re.sub(r'NNN',str(counter),div)
        # Replace RE_URL placeholder with URL for redirection.
        if "url" in config[configCounter(counter)]:
            div = re.sub(r'RE_URL',config[configCounter(counter)]["url"],div)
        # Discription
        if "discription" in config[configCounter(counter)]:
            div = re.sub(r'DISCRIPTION',config[configCounter(counter)]["discription"],div)
        if session != "":
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

    scenario = config[configCounter(counter)]["scenario"]
    if scenario == "PART":
        print "Proceed to next block " + str(counter+1)
        result = result + "<div class=displayblock id=out" + str(counter) + "></div>\n"
        counter, result = getNext(counter+1, result, session, True)
    print "End of getNext "+ str(counter)
    return counter, result
# End of getNext(counter=None, result="")


# Translate block counter into numbering in config YAML.
# In YAML block numbers begin with 0.
# In brower block numbers start from 1.
def configCounter(counter):
    return int(counter - 1)


# Rreturn javascript for refreshing current div
def RefreshScript(session, counter):
    script = '''
        <script>
        var active_refresh = 1; // Autoreload div contents with timeout.
        var load_next = 1;   // Load next block when output loaded to the end.
        function refreshDiv() {
            if (active_refresh) {
                console.log("Requesting /readoutput?session='''+session+"&block="+counter+'''");
                $("#out'''+counter+'''").load("/readoutput?session='''+session+"&block=" + counter + '''", function() {
                    this.scrollTop = this.scrollHeight;
                    if (active_refresh) {
                        setTimeout( refreshDiv, 2000);
                        console.log("Output updated. Refreshing in 2 sec.");
                    }
                });
            }
        };
        if (active_refresh) {
            console.log("Refreshing in 2s - "+active_refresh);
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
    output_file = open(outfilename, 'w')
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


# Set envvars.
# Arguments format:
# args = {'key':'value', ...}
# allowed = {'var':'default value', ...}
#
# Add allowed assignment to env_vars.
# Save variables in dictionary with session name.
# If no session provided use "nosession" name.
def parseVars(args,allowed,session=""):
    global env_vars
    newvars=dict()
    if session != "":
        dict_name = str(session)
    else:
        dict_name = "nosession"
    if dict_name not in env_vars.keys() or env_vars[dict_name] is None:
        env_vars[dict_name] = dict()
    print "Have args in parseVars: " + str(args)
    # Loop through parsed object attributes
    for key, value in args.iteritems():
            key = str(key)  # Convert from Unicode
            value = str(value)
            print "key:"+key + " val:"+ str(value)
            if key in allowed or len(allowed) == 0:
                print key + " OK (" + str(len(allowed)) + ")"
                newvars[key] = value
    env_vars[dict_name].update(newvars)


# Execute command in shell
# and return its stdout and stderr streams.
def Execute(command) :
    print "Executing " + command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output = [l.decode('utf8') for l in proc.stdout.readlines()]
    err = [l.decode('utf8') for l in proc.stderr.readlines()]
    return (output, err)


# HTML-sanitation
conv = Ansi2HTMLConverter(inline=True)

# Replace symbols that can destroy html in browser.
def html_safe(data):
    data = conv.convert(data,full=False)
    return data


# Shutdown server
def shutdown(session=""):
    global static_folder
    global sleep_time
    print "Shutting down"
    sleep(sleep_time + 1)
    if session != "":
        # Remove session files
        shutil.rmtree(sessionDir(session))
    pid = os.getpid()
    print "PID\t"+str(pid)
    ps = subprocess.check_output(["ps","-p",str(pid)])
    print ps
    subprocess.check_call(["kill",str(pid)])

bottle.run(webint,host='0.0.0.0', port=8080, debug=True, server=GeventWebSocketServer)
