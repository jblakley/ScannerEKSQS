import sys
import os.path
import subprocess as sp
import getpass
from optparse import OptionParser
import time
from tqdm import tqdm

VPC_STACK_NAME = "eks-vpc" # TODO include in parameters, defaults and interactive
AWSACCT = "601041732504" # TODO include in parameters, defaults and interactive
SLEEPTIME = 10

def main():
    numberNodes = None    
    
    try:
        print("# Start Cluster Builder")
        
        ''' App Setup '''
        parser = OptionParser()
        parser.add_option("-c", "--clustername", dest="clustername",
                      help="use NAME as clustername", metavar="NAME")
        parser.add_option("-n", "--nodes", dest="numberofnodes",
                      help="use INT as number of nodes # TODO", metavar="INT")
        parser.add_option("-C", "--create",
                      action="store_true", dest="create", default=False,
                      help="Create the cluster")
        parser.add_option("-D", "--deploy",
                      action="store_true", dest="deploy", default=False,
                      help="Build and Deploy the cluster")
        parser.add_option("-S", "--staging",
                      action="store_true", dest="staging", default=False,
                      help="Make this instance a staging machine #TODO") #TODO
        parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=False,
                      help="Print debugging information")
        parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Print detailed information #TODO")
    
        (options, args) = parser.parse_args()
        
        clusterName = options.clustername
        numberNodes = options.numberofnodes
        verboseOn = options.verbose
        createCluster = options.create
        deployCluster = options.deploy
        debugOn = options.debug
        buildStaging = options.staging

        while clusterName is None:
            clusterName = input("Enter clustername: ")
        if createCluster:
            while numberNodes is None:
                numberNodes = input("Enter number of nodes: ")
                
        kwargs = {'CLUSTER_NAME':clusterName, 'NUMNODES':numberNodes, 
                  'VERBOSE':verboseOn, 'DEBUG':debugOn, 
                  'HOME':os.environ['HOME'], 'USER':os.environ['USER'],
                  'VPC_STACK_NAME':VPC_STACK_NAME,'AWSACCT':AWSACCT}

        # TODO error handling for missing values, **kwargs
        
        set_environ(kwargs)
        
        ''' End Setup '''

        ''' App Run '''
        if createCluster is True:
            create_cluster(kwargs)
        setKubeconfig(kwargs)
        oscmd("kubectl get nodes")
        oscmd("env")
        if deployCluster is True:
            deploy_k8s(kwargs)
        wait_for_deployment()
        print("Wait for cluster to settle before running smoke test")
        for ii in tqdm(range(60)):
            time.sleep(1) # Wait for the cluster to settle down TODO -- make deterministic
        run_smoke()
   
        print ("# Completed Processing --> Exiting")
    except KeyboardInterrupt:
        sys.exit(0)
def create_cluster(kwargs):
    # Need to check if cluster already exists TODO
    cn = kwargs['CLUSTER_NAME']
    nn = kwargs['NUMNODES']
    os.environ['NUMNODES'] = nn
    print("Creating cluster with name: %s and %s nodes" % (cn,nn))

    if kwargs['DEBUG']:
        dbgstr = "-vx"
    else:
        dbgstr = ""
    cmdstr = ("bash %s ./create_eks_cluster.sh %s %s" % (dbgstr,cn,nn))
    oscmd(cmdstr)
    # Need to check for success TODO

def deploy_k8s(kwargs):
    print("Deploying cluster %s" % kwargs['CLUSTER_NAME'])
    if kwargs['DEBUG']:
        dbgstr = "-vx"
    else:
        dbgstr = ""
    cmdstr = ("bash %s ./build_and_deploy.sh" % dbgstr)
    oscmd(cmdstr)
    # Need to check for success
def wait_for_deployment():
    while True:
        oscmd('kubectl get pods')
        workerpodsall = int(sp.check_output(
        '''
        kubectl get pods|egrep -e "worker"|wc|awk '{print $1}'
        ''',
        shell=True).strip().decode('utf-8'))
        workerpodsrunning = int(sp.check_output(
        '''
        kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}'
        ''',
        shell=True).strip().decode('utf-8'))
        if workerpodsall == workerpodsrunning:
            break
        time.sleep(SLEEPTIME)
    pass

def run_smoke():
    cmdstr = ("python3 smoketest.py")
    oscmd(cmdstr)
    pass

# App Utilities
def setKubeconfig(kwargs):
    # Check me first
    meName = kwargs['USER']
    clusterName = kwargs['CLUSTER_NAME']
    homeDir = kwargs['HOME']

    myKube = "/%s/.kube/config-%s" % (meName,clusterName)
    if os.path.isfile(myKube):
        os.environ['KUBECONFIG'] = myKube
        pass
    else:
        homeKube = "%s/.kube/config-%s" % (homeDir,clusterName)
        if os.path.isfile(homeKube):
            os.environ['KUBECONFIG'] = homeKube
        
def getAWScred():
    accessk = sp.check_output(
        '''
        grep aws_access_key_id ~/.aws/credentials|cut -f2 -d "="
        ''',
        shell=True).strip().decode('utf-8')
    secretk = sp.check_output(
        '''
        grep aws_secret_access_key ~/.aws/credentials|cut -f2 -d "="
        ''',
        shell=True).strip().decode('utf-8')
    os.environ['AWS_ACCESS_KEY_ID'] = accessk
    os.environ['AWS_SECRET_ACCESS_KEY'] = secretk
    pass

def oscmd(cmdstr):
    os.system(cmdstr)

def set_environ(kwargs):
    getAWScred() 
    os.environ['CLUSTER_NAME'] = kwargs['CLUSTER_NAME']
    # make sure that current directory is in PATH
    os.environ['PATH'] = os.environ['PATH'] + ":."


def cmd(cmdstr):
    output = os.popen(cmdstr).read().split("\n")
    return output

if __name__ == '__main__': main()
