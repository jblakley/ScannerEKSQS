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
    
    global debugOn
    
    maxNodes = 4
    nodesDesired = 2    
    
    try:
        print("# Start Cluster Builder")
        
        ''' App Setup '''
        parser = OptionParser()
        parser.add_option("-c", "--clustername", dest="clustername",
                      help="use NAME as clustername", metavar="NAME")
        parser.add_option("-n", "--nodesdesired", dest="nodesdesired",
                      help="use INT as number of desired nodes in the cluster", metavar="INT")
        parser.add_option("-m", "--maxnodes", dest="maxnodes",
                      help="use INT as number of maximum nodes in the cluster # TODO", metavar="INT")
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
        
        buildStaging = options.staging
        createCluster = options.create
        deployCluster = options.deploy
        stagingMachineBuild = options.staging
              
        if options.maxnodes is not None:
            maxNodes = int(options.maxnodes)
        if options.nodesdesired is not None:     
            nodesDesired = int(options.nodesdesired)
        if maxNodes < nodesDesired:
            print ("Maxnodes (%i) must be >= Nodesdesired (%i)\nMaxnodes set to Nodesdesired" % (maxNodes, nodesDesired))
            maxNodes = nodesDesired
        if nodesDesired < 2:
            print ("Nodesdesired (%i) must be >1" % (nodesDesired))
            exit(1)

        clusterName = options.clustername
        while clusterName is None:
            clusterName = input("Enter clustername: ")

        verboseOn = options.verbose

        debugOn = options.debug

        kwargs = {'CLUSTER_NAME':clusterName, 'MAXNODES':maxNodes, 'NODESDESIRED':nodesDesired, 
                  'VERBOSE':verboseOn, 'DEBUG':debugOn, 
                  'HOME':os.environ['HOME'], 'USER':os.environ['USER'],
                  'VPC_STACK_NAME':VPC_STACK_NAME,'AWSACCT':AWSACCT}

        # TODO error handling for missing values, **kwargs -- pretty print kwargs
        
        set_environ(kwargs)
        
        ''' End Setup '''

        ''' App Run '''
        if stagingMachineBuild is True:
            build_staging_machine(kwargs)

        if createCluster is True:
            create_cluster(kwargs)
        if not isEKSCluster(clusterName):
            print("No such cluster: %s -- exiting" % clusterName)
            sys.exit(1)
        setKubeconfig(kwargs)
        wait_for_cluster()
        scale_cluster(kwargs)
        wait_for_cluster()        
        oscmd("env")
        if deployCluster is True:
            deploy_k8s(kwargs)
            wait_for_deployment()
            run_smoke()
   
        print ("# Completed Processing --> Exiting")
        print ("#\tDon't forget to run:\n#\t\t. ./setkubectl.sh %s" % clusterName)
        print ("#\t\texport LD_LIBRARY_PATH=/usr/lib:/usr/local/lib")
        
    except KeyboardInterrupt:
        sys.exit(0)
def build_staging_machine(kwargs):
    print("Building staging machine")
    cmdstr = ("bash %s ./build_staging_machine.sh" % getDBGSTR())
    oscmd(cmdstr)   
def create_cluster(kwargs):
    # Need to check if cluster already exists TODO
    cn = kwargs['CLUSTER_NAME']
    
    if isEKSCluster(cn):
        print("Cluster %s already exists -- can't create -- proceeding")
        return
    nn = str(kwargs['MAXNODES'])
    os.environ['MAXNODES'] = nn
    print("Creating cluster with name: %s and %s nodes" % (cn,nn))
    cmdstr = ("bash %s ./create_eks_cluster.sh %s %s" % (getDBGSTR(),cn,nn))
    oscmd(cmdstr)
    # Need to check for success TODO

def deploy_k8s(kwargs):
    print("Deploying cluster %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./build_and_deploy.sh" % getDBGSTR())
    oscmd(cmdstr)
    # Need to check for success


def wait_for_cluster():
    SETTLETIME = 30 # seconds
    if not is_cluster_running():    
        while True:
            wait_bar(SLEEPTIME)
            if is_cluster_running():
                break
            wait_bar(SETTLETIME)
#     print()
def is_cluster_running():
    oscmd('kubectl get nodes')
    nodessall = int(sp.check_output(
    '''
    kubectl get nodes|grep -v "NAME"|wc|awk '{print $1}'
    ''',
    shell=True).strip().decode('utf-8'))
    nodesrunning = int(sp.check_output(
    '''
    kubectl get nodes|egrep "Ready"|wc|awk '{print $1}'
    ''',
    shell=True).strip().decode('utf-8'))
    if nodessall == nodesrunning:
        return True
    else:
        return False
def wait_for_deployment():
    SETTLETIME = 120 # seconds
    if not is_deployment_running():
        while True:
            wait_bar(SLEEPTIME)
            if is_deployment_running():
                break            
            wait_bar(SETTLETIME)
def is_deployment_running():
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
        return True
    else:
        return False
def run_smoke():
    cmdstr = ("python3 smoketest.py")
    oscmd(cmdstr)
    pass
def scale_cluster(kwargs):
    cmdstr = ("bash %s scalecluster.sh %i" % (getDBGSTR(),kwargs['NODESDESIRED']))
    oscmd(cmdstr)
    pass
def scale_deployment(kwargs):
    cmdstr = ("bash %s scaledeployment.sh" % getDBGSTR())
    oscmd(cmdstr)
    pass
def scale_autoscaling_group(kwargs):
    cmdstr = ("bash %s scaleasg.sh %i" % (getDBGSTR(),kwargs['NODESDESIRED']))
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
def isEKSCluster(cname):
    if cname in getEKSClusters():
        return True
    else:
        return False
def getEKSClusters():
    clusters = sp.check_output(
        '''
        aws eks list-clusters |jq -r '.clusters[]'
        ''',
        shell=True).strip().decode('utf-8')
    return clusters

def getDBGSTR():
    if debugOn:
        return "-vx"
    else:
        return ""
def wait_bar(seconds):
    wait_range = tqdm(range(seconds))
#     wait_range = tqdm(range(seconds),file=sys.stdout)    
    for ii in wait_range:
        wait_range.refresh()
        time.sleep(1)
    wait_range.write("DONE", file=None, end='\n', nolock=False)
    wait_range.close()
#     print("", file=sys.stderr)
    print()

def oscmd(cmdstr):
    os.system(cmdstr)

def set_environ(kwargs):
    getAWScred() 
    os.environ['CLUSTER_NAME'] = kwargs['CLUSTER_NAME']
    os.environ['NODESDESIRED'] = str(kwargs['NODESDESIRED'])
    os.environ['MAXNODES'] = str(kwargs['MAXNODES'])
    os.environ['LD_LIBRARY_PATH'] = "/usr/lib:/usr/local/lib" # Scanner needs this
    # make sure that current directory is in PATH
    os.environ['PATH'] = os.environ['PATH'] + ":."


def cmd(cmdstr):
    output = os.popen(cmdstr).read().split("\n")
    return output

if __name__ == '__main__': main()
