#!/bin/bash

for i in {1..5}; do
    echo "test $1 I=$i"
    sleep 1
    echo "err" 1>&2
    sleep 1
done
