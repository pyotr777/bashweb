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
        fd.close()

if __name__ == "__main__":
    pp = pprint.PrettyPrinter(indent=4)
    filepath = "./webfiles/config/script_3.yml"
    data = yaml_load(filepath)
    print "-------"
    pp.pprint(data)
    print "-------"
    pp.pprint(data[0])
    print data[6]["scenario"]
    print "-------"
    print len(data)
    print yaml.dump(data)