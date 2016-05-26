#!/usr/bin/env python

from bottle import route, run
import subprocess
import re

# Substitutions
subst = ["","-"]



@route('/')
@route('/hello')
def hello():
    return "Hello World!"

@route('/exec/<esc_command>')
def exec_command(esc_command='pwd'):
    command = esc_command.split("_")
    try:
        output = subprocess.check_output(command,stderr=subprocess.STDOUT)
        #output = re.sub(subst[0],subst[1],output)
    except subprocess.CalledProcessError as ex:
        return "Error. cmd='"+ " ".join(ex.cmd)+ "' returncode="+ str(ex.returncode)
    else:        
        return "<html>\n<pre>\n"+output+"</pre>\n</html>"

run(host='localhost', port=8080, debug=True)
