#!/bin/bash

KP_VAR=VAL

read -rd '' testvar <<EOF
drwxr-xr-x  7 kportal kportal 4096 Aug  5 09:58 \033[0m\033[01;34m.\033[0m
drwxr-xr-x  4 root    root    4096 Aug  5 07:50 \033[01;34m..\033[0m
drwxrwxr-x  3 kportal kportal 4096 Aug  5 08:08 \033[01;34minstall\033[0m
drwxrwxrwx  2 kportal kportal 4096 Aug  5 08:11 \033[34;42mlog\033[0m
-rw-r--r--  1 kportal kportal  675 Apr  9  2014 .profile
drwxr-xr-x 17 kportal kportal 4096 Aug  5 09:49 \033[01;34msrc\033[0m

EOF

echo -en "$testvar"
echo -en "\033[38;5;50m#####\033[m\n"
echo -en "python\nprint \"sd\"\n<script> alert(!); </script>\n"
echo -en "\\ \\\ df\"string? <br/>//&lt;<p>\n"
echo "KP_VAR is $KP_VAR "

ls -lGa