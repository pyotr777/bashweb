#!/bin/bash

for i in {1..100}; do
    echo "test $1"
    echo "I=$i"
    echo "err" 1>&2
    sleep 0.01
done
sleep 1
for i in {1..17}; do
    echo "test $1"
    echo "I=$i"
    echo "err" 1>&2
    sleep 0.1
done

