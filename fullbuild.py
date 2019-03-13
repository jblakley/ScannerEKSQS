import sys
import os.path
import subprocess as sp
import getpass
from optparse import OptionParser

VPC_STACK_NAME = "eks-vpc" # TODO include in parameters, defaults and interactive
AWSACCT = "601041732504" # TODO include in parameters, defaults and interactive


def main():

    global debugOn
    global verboseOn
    global clusterName
    try:
        print("# Start Cluster QuickStart")
        
        parser = OptionParser()
        parser.add_option("-c", "--clustername", dest="clustername",
                      help="use NAME as clustername", metavar="NAME")
        parser.add_option("-n", "--numberofnodes", dest="numberofnodes",
                      help="use INT as number of nodes", metavar="INT")
        parser.add_option("-C", "--create",
                      action="store_true", dest="create", default=False,
                      help="Create the cluster")
        parser.add_option("-D", "--deploy",
                      action="store_true", dest="deploy", default=False,
                      help="Build and Deploy the cluster")
        parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=False,
                      help="Print detailed information")
        parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Print detailed information")
    
        (options, args) = parser.parse_args()
        
        clusterName = options.clustername
        numberNodes = options.numberofnodes
        verboseOn = options.verbose
        createCluster = options.create
        deployCluster = options.deploy
        debugOn = options.debug
        
        homeDir = os.path.expanduser('~')
        meName = getpass.getuser()
#         setKubeconfig(homeDir, meName)
        
        if clusterName is None:
            clusterName = input("Enter clustername: ")
        if numberNodes is None:
            numberNodes = input("Enter number of nodes: ")
            
        # TODO error handling for missing values, **kwargs
        
        if createCluster is True:
            create_cluster(numberNodes)
        setKubeconfig(homeDir, meName)
        if deployCluster is True:
            deploy_k8s()
            run_smoke()
   
        print ("# Completed Processing --> Exiting")
    except KeyboardInterrupt:
        sys.exit(0)
def create_cluster(nn):
    # Need to check if cluster already exists TODO
    cn = clusterName
    print("Creating cluster with name: %s and %s nodes" % (cn,nn))

    if debugOn:
        dbgstr = "-vx"
    else:
        dbgstr = ""
    cmdstr = ("bash %s ./create_eks_cluster.sh %s %s" % (dbgstr,cn,nn))
    oscmd(cmdstr)
    # Need to check for success TODO

def deploy_k8s():
    print("Deploying cluster %s" % clusterName)
    if debugOn:
        dbgstr = "-vx"
    else:
        dbgstr = ""
    cmdstr = ("bash %s ./build_and_deploy.sh" % dbgstr)
    oscmd(cmdstr)
    # Need to check for success

def run_smoke():
    cmdstr = ("python3 smoketest.py")
    oscmd(cmdstr)
    pass

# App Utilities
def setKubeconfig(homeDir, meName):
    # Check me first
    myKube = "/%s/.kube/config-%s" % (meName,clusterName)
    if os.path.isfile(myKube):
        os.environ['KUBECONFIG'] = myKube
        pass
    else:
        homeKube = "%s/.kube/config-%s" % (homeDir,clusterName)
        if os.path.isfile(homeKube):
            pass
        

def oscmd(cmdstr):
    osset_environ()
    os.system(cmdstr)

def osset_environ():
    os.environ['CLUSTER_NAME'] = clusterName


def cmd(cmdstr):
    output = os.popen(cmdstr).read().split("\n")
    return output

if __name__ == '__main__': main()
