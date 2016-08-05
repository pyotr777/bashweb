#!/bin/bash
#
# generates an 8 bit color table (256 colors) for
# reference purposes, using the \033[48;5;${val}m
# ANSI CSI+SGR (see "ANSI Code" on Wikipedia)
#

echo -en "\n   +  "
for i in {0..5}; do
  printf "%3b       " $i
done

printf "\n\n %3b  " 0
for i in {0..5}; do
  echo -en "\033[48;5;${i}m ### \033[m     "
done

printf "\n\n %3b  " 6
for i in {0..5}; do
  echo -en "\033[48;5;${i}m ### \033[m     "
done

printf "\n\n %3b  " 12
for i in {0..5}; do
  echo -en "\033[48;5;${i}m ### \033[m     "
done

#for i in 16 52 88 124 160 196 232; do
for i in {0..39}; do
  let "i = i*6+16"
  printf "\n\n %3b  " $i
  for j in {0..5}; do
    let "val = i+j"
    printf "\033[48;5;${val}m#%3b\033[m\033[38;5;${val}m#%3b\033[m  " $val $val
    #echo -en "\033[48;5;${val}m #$val \033[m \033[38;5;${val}m #$val \033[m "
  done
done

echo -e "\n"
