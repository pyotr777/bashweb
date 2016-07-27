#!/bin/bash

for i in {1..10}; do
    echo "test $1"
    echo "I=$i"
    sleep 1
    echo "err" 1>&2
    sleep 2
done
