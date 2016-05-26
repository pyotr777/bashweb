#!/usr/bin/env python

import bottle
import subprocess
import re

# Substitutions
subst = ["","-"]
# Permitted hosts
accessList = ["localhost","127.0.0.1"]

# Check access origin
def allowAccess():
    remoteaddr = bottle.request.environ.get('REMOTE_ADDR')
    forwarded = bottle.request.environ.get('HTTP_X_FORWARDED_FOR')

    if (remoteaddr in accessList) or (forwarded in accessList):
        return True
    else:
        return False


@bottle.route('/')
@bottle.route('/hello')
def hello():
    return "Hello World!"

@bottle.route('/exec/<esc_command>')
def exec_command(esc_command='pwd'):
    if allowAccess():
        pass
    else:
        return "Access dinied"

    command = esc_command.split("_")
    try:
        output = subprocess.check_output(command,stderr=subprocess.STDOUT)
        #output = re.sub(subst[0],subst[1],output)
    except subprocess.CalledProcessError as ex:
        return "Error. cmd='"+ " ".join(ex.cmd)+ "' returncode="+ str(ex.returncode)
    else:        
        return "<html>\n<pre>\n"+output+"</pre>\n</html>"

@bottle.route('/myhost')
def display_remote_host():
    return bottle.request.environ.get('REMOTE_ADDR')

bottle.run(host='localhost', port=8080, debug=True)

