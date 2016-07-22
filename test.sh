#!/bin/bash

for i in {1..5}; do
    echo "I=$i"
    sleep 1
    echo "err" 1>&2
    sleep 1
done
