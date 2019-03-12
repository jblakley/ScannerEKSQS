import cv2
import sys
import os.path
import subprocess as sp
from optparse import OptionParser

def main():

    try:
        print("# Start Cluster QuickStart")
        
        parser = OptionParser()
        parser.add_option("-c", "--clustername", dest="clustername",
                      help="use NAME as clustername", metavar="NAME")
        parser.add_option("-n", "--numberofnodes", dest="numberofnodes",
                      help="use INT as number of nodes", metavar="INT")
        parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Print detailed information")
    
        (options, args) = parser.parse_args()
        
        clusterName = options.clustername
        numberNodes = options.numberofnodes
        verbose = options.verbose
        
        if clusterName is None:
            clusterName = input("Enter clustername: ")
        if numberNodes is None:
            numberNodes = input("Enter number of nodes: ")

        create_cluster(clusterName, numberNodes)
        deploy_k8s()
        run_smoke()
   
        print ("# Completed Processing --> Exiting")
    except KeyboardInterrupt:
        sys.exit(0)
def create_cluster(cn,nn):
    # Need to check if cluster already exists TODO
    cmdstr = ("bash ./create_eks_cluster.sh %s %s" % (cn,nn))
    oscmd(cmdstr)
    # Need to check for success TODO

def deploy_k8s():
    cmdstr = ("bash ./build_and_deploy.sh")
    oscmd(cmdstr)
    # Need to check for success

def run_smoke():
    cmdstr = ("python3 smoketest.py")
    oscmd(cmdstr)
    pass

def oscmd(cmdstr):
    os.system(cmdstr)

def cmd(cmdstr):
    output = os.popen(cmdstr).read().split("\n")
    return output

if __name__ == '__main__': main()
