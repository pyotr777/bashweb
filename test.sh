#!/bin/bash

for i in {1..2}; do
    echo "test $1"
    echo "I=$i"
    sleep 0.1
    echo "err" 1>&2
    sleep 0.1
done
