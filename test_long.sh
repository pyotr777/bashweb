#!/bin/bash

for i in {1..100}; do
    echo "test $1"
    echo "I=$i"
    echo "err" 1>&2
    sleep 0.05
done
sleep 3
echo "TERM $TERM"
echo "SHELL $SHELL"
echo "CC $CLICOLOR"
export CLICOLOR_FORCE=1
echo "CC_F $CLICOLOR_FORCE"

ls

