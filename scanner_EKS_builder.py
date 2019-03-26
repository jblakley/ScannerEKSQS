import sys
import os.path
import subprocess as sp
import getpass
from optparse import OptionParser
import time
import json
from tqdm import tqdm


SLEEPTIME = 10


def main():
    ''' Default Parameters '''
    VPC_STACK_NAME = "VPC_STACK_NAME_DEFAULT" 
    AWSACCT = "AWSACCT_DEFAULT"
    CONFIGFILE = "seb_config.json"
    CONTAINER_TAG = "scannerresearch/scanner:cpu-latest"
    
    global debugOn
    global verboseOn
    
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
        parser.add_option("-B", "--build",
                      action="store_true", dest="build", default=False,
                      help="Build the deployment for the cluster")
        parser.add_option("-D", "--deploy",
                      action="store_true", dest="deploy", default=False,
                      help="Build and Deploy the cluster")
        parser.add_option("-S", "--staging",
                      action="store_true", dest="staging", default=False,
                      help="Make this instance a staging machine")
        parser.add_option( "-e", "--delete",
                      action="store_true", dest="delete", default=False,
                      help="delete the cluster TODO")
        parser.add_option("-j", "--jsonconfig", dest="jsonconfig",
                      help="use NAME as json configuration file", metavar="NAME")
        parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=False,
                      help="Print debugging information")
        parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Print detailed information #TODO")
    
        (options, args) = parser.parse_args()
        configJSON = options.jsonconfig
        
        # need to finish -- load config file then override with new data from command line
        ''' Options Priority:
            1) Command line override
            2) Configuration file
            3) Default values
        '''
        
        ''' Configuration file '''
        if configJSON is None:
            configJSON = CONFIGFILE
        
        if os.path.isfile(configJSON):
            with open(configJSON) as jfile:
                jdata = json.load(jfile)
                for key in jdata.keys():
                    if key == 'maxNodes':
                        maxNodes = jdata[key]
                    elif key == 'nodesDesired':
                        nodesDesired = jdata[key]
                    elif key == 'region':
                        awsRegion = jdata[key]
                    elif key == 'account':
                        AWSACCT = jdata[key]                        
                    elif key == 'clusterName':
                        clusterName = jdata[key]
                    elif key == 'CONTAINER_TAG':
                        CONTAINER_TAG = jdata[key]
                    elif key == 'VPC_STACK_NAME':
                        VPC_STACK_NAME = jdata[key]
                    elif key == 'BUCKET':
                        BUCKET = jdata[key]
        else:
            print("Configuration file %s does not exist" % configJSON)
            exit(1)
        
        ''' Only set on command line '''
        verboseOn = options.verbose
        debugOn = options.debug

        buildStaging = options.staging
        createCluster = options.create
        buildDeployment = options.build        
        deployCluster = options.deploy
        deleteCluster = options.delete

        
        ''' Command line overrides '''
        if options.maxnodes is not None:
            maxNodes = int(options.maxnodes)
        if options.nodesdesired is not None:     
            nodesDesired = int(options.nodesdesired)
        ''' Node mix validation -- maxNodes > nodesDesired and nodesDesired > 2 (one worker, one master) '''
        if maxNodes < nodesDesired:
            print ("Maxnodes (%i) must be >= Nodesdesired (%i)\nMaxnodes set to Nodesdesired" % (maxNodes, nodesDesired))
            maxNodes = nodesDesired
        if nodesDesired < 2:
            print ("Nodesdesired (%i) must be >1" % (nodesDesired))
            exit(1)

        if options.clustername is not None:
            clusterName = options.clustername
        while clusterName is None:
            clusterName = input("Enter clustername: ")
        
        ''' The following don't (yet) have comand line overrides -- HOME, USER, VPC_STACK_NAME, BUCKET,  AWSACCT, REGION '''
        kwargs = {'CLUSTER_NAME':clusterName, 'MAXNODES':maxNodes, 'NODESDESIRED':nodesDesired, 
                  'VERBOSE':verboseOn, 'DEBUG':debugOn, 
                  'HOME':os.environ['HOME'], 'USER':os.environ['USER'],
                  'VPC_STACK_NAME':VPC_STACK_NAME,
                  'CONTAINER_TAG':CONTAINER_TAG,
                  'AWSACCT':AWSACCT,'REGION':awsRegion, 'BUCKET':BUCKET }

        # TODO error handling for missing values, **kwargs -- pretty print kwargs
        
        set_environ(kwargs)
        
        ''' End Setup '''

        ''' App Run '''
        
        if deleteCluster is True:
            delete_cluster(kwargs)
            sys.exit(0)
        if buildStaging is True:
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
        if buildDeployment is True:
            build_deployment(kwargs)
        if deployCluster is True:
            deploy_k8s(kwargs)
            wait_for_deployment()
            run_smoke()
        create_setK8SSenv(kwargs)
        print ("# Completed Processing --> Exiting")
        print ("#\tDon't forget to run:\n\t. ./setK8SSenv.sh")
        
        ''' End App Run '''
        
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

def build_deployment(kwargs):
    print("Deploying deployment for %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./build_deployment.sh" % getDBGSTR())
    oscmd(cmdstr)

def deploy_k8s(kwargs):
    print("Deploying cluster %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./deploy.sh" % getDBGSTR())
    oscmd(cmdstr)
    # Need to check for success

def delete_cluster(kwargs):
    print("Deleting cluster %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./delete_eks_cluster.sh %s" % (getDBGSTR(), kwargs['CLUSTER_NAME']))
    oscmd(cmdstr)

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
        grep aws_access_key_id /root/.aws/credentials|cut -f2 -d "="
        ''',
        shell=True).strip().decode('utf-8')
    secretk = sp.check_output(
        '''
        grep aws_secret_access_key /root/.aws/credentials|cut -f2 -d "="
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

def create_setK8SSenv(kwargs):
    fname = "setK8SSenv.sh"
    filed = open(fname,"w")
    for evar in ['KUBECONFIG', 'LD_LIBRARY_PATH','PATH','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','CLUSTER_NAME']:
        filed.write("export %s=%s\n" % (evar,os.environ[evar]))
    filed.close()
def getDBGSTR():
    if debugOn:
        return "-vx"
    else:
        return ""
def wait_bar(seconds):
    wait_range = tqdm(range(seconds)) 
    for ii in wait_range:
        wait_range.refresh()
        time.sleep(1)
    wait_range.write("DONE", file=None, end='\n', nolock=False)
    wait_range.close()
    print()

def oscmd(cmdstr):
    os.system(cmdstr)

def set_environ(kwargs):
    # Fix for root with bad home (ubuntu 16.04)
    if kwargs['USER'] == 'root' and kwargs['HOME'] != '/root':
        kwargs['HOME'] = '/root'
        os.environ['HOME'] = '/root'
    getAWScred() 
    for envvar in ['CLUSTER_NAME','AWSACCT','REGION','NODESDESIRED','MAXNODES','VPC_STACK_NAME','CONTAINER_TAG','BUCKET']:
        os.environ[envvar] = kwargs[envvar]
#     os.environ['CLUSTER_NAME'] = kwargs['CLUSTER_NAME']
#     os.environ['AWSACCT'] = kwargs['AWSACCT']
#     os.environ['REGION'] = kwargs['REGION']    
#     os.environ['NODESDESIRED'] = str(kwargs['NODESDESIRED'])
#     os.environ['MAXNODES'] = str(kwargs['MAXNODES'])
#     os.environ['VPC_STACK_NAME'] = kwargs['VPC_STACK_NAME']
#     os.environ['CONTAINER_TAG'] = kwargs['CONTAINER_TAG']
#     os.environ['BUCKET'] = kwargs['BUCKET']

    # Get paths right
    os.environ['LD_LIBRARY_PATH'] = "/usr/lib:/usr/local/lib" # Scanner needs this
    os.environ['PATH'] = os.environ['PATH'] + ":."


def cmd(cmdstr):
    output = os.popen(cmdstr).read().split("\n")
    return output

if __name__ == '__main__': main()
