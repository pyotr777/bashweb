#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CHITEC, Stair Lab

import yaml
import pprint

def yaml_load(filepath):
    with open(filepath,"r") as fd:
        data = yaml.load(fd)
    return data

def yaml_dump(filepath, data):
    with open(filepath, "w") as fd:
        yaml.dump(data, fd)

if __name__ == "__main__":
    pp = pprint.PrettyPrinter(indent=4)
    filepath = "./webfiles/static/config/script_2.yml"
    data = yaml_load(filepath)
    #pp.pprint(data)
    pp.pprint(data[2]["scenario"])
    if data[5]["scenario"] == "PART":
        print "Sc.5 is PART"
    #yaml_dump("dump.yml", data)