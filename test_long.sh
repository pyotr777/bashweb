#!/bin/bash

for i in {1..100}; do
    echo "test $1"
    echo "I=$i"
    echo "err" 1>&2
    sleep 0.05
done
