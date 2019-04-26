#!/usr/bin/env python3
import sys
import os.path
import subprocess as sp
from optparse import OptionParser
import time
import json
from tqdm import tqdm


SLEEPTIME = 10


def main():
    ''' Default Parameters '''
    VPC_STACK_NAME = "" 
    AWSACCT = ""
    CONFIGFILE = "seb_config.json"
    CONTAINER_TAG = "scannerresearch/scanner:cpu-latest"
    INSTANCE_TYPE = "c4.8xlarge"
    
    global debugOn
    global verboseOn
    
    maxNodes = 4
    nodesDesired = 2
    KEYNAME=""
    
    try:
        print("# Start Cluster Builder")
        
        ''' App Setup '''
        parser = OptionParser()
        parser.add_option("-c", "--clustername", dest="clustername",
                      help="use NAME as clustername", metavar="NAME")
        parser.add_option("-n", "--nodesdesired", dest="nodesdesired",
                      help="use NODES as number of desired nodes in the cluster", metavar="NODES")
        parser.add_option("-m", "--maxnodes", dest="maxnodes",
                      help="use MAXNODES as number of maximum nodes in the cluster (only on create)", metavar="MAXNODES")
        parser.add_option("-i", "--instancetype", dest="instancetype",
                      help="Use instance type INSTANCE in cluster", metavar="INSTANCE")
        parser.add_option("-C", "--create",
                      action="store_true", dest="create", default=False,
                      help="Create the cluster")
        parser.add_option("-B", "--build",
                      action="store_true", dest="build", default=False,
                      help="Build the deployment for the cluster")
        parser.add_option("-D", "--deploy",
                      action="store_true", dest="deploy", default=False,
                      help="Deploy the cluster")
        parser.add_option("-S", "--staging",
                      action="store_true", dest="staging", default=False,
                      help="Make this instance a staging machine")
        parser.add_option("-G", "--scale",
                      action="store_true", dest="scale", default=False,
                      help="Scale the cluster and deployment to specified desired nodes (with -n option)")
        parser.add_option("-H", "--halt",
                      action="store_true", dest="halt", default=False,
                      help="Halt the cluster by changing autoscaling group desired size to 0")  
        parser.add_option("-T", "--smoke",
                      action="store_true", dest="smoke", default=False,
                      help="Try out your cluster by running a smoke test")
        parser.add_option( "-e", "--delete",
                      action="store_true", dest="delete", default=False,
                      help="delete the cluster")
        parser.add_option("-j", "--jsonconfig", dest="jsonconfig",
                      help="use FILE.json as configuration file", metavar="FILE.json")
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
        
        if not os.path.isfile(configJSON):
            create_config(configJSON)
            
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
                elif key == 'KEYNAME':
                    KEYNAME = jdata[key]
                elif key == 'INSTANCE_TYPE':
                    INSTANCE_TYPE = jdata[key]                        

        
        ''' Only set on command line '''
        verboseOn = options.verbose
        debugOn = options.debug

        buildStaging = options.staging
        createCluster = options.create
        buildDeployment = options.build        
        deployCluster = options.deploy
        deleteCluster = options.delete
        scaleCluster = options.scale
        haltCluster = options.halt
        runSmoke = options.smoke

        
        ''' Command line overrides '''
        ''' The following don't (yet) have comand line overrides -- HOME, USER, VPC_STACK_NAME, BUCKET,  AWSACCT, REGION '''

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
        if options.instancetype is not None:
            INSTANCE_TYPE = options.instancetype

        if options.clustername is not None:
            clusterName = options.clustername
        
        ''' Complete any required options by user input '''
        while clusterName is None:  # TODO is this needed anymore?
            clusterName = input("Enter clustername: ")
        
        kwargs = {'CLUSTER_NAME':clusterName, 'MAXNODES':maxNodes, 'NODESDESIRED':nodesDesired, 
                  'VERBOSE':verboseOn, 'DEBUG':debugOn, 
                  'HOME':os.environ['HOME'], 'USER':os.environ['USER'],
                  'VPC_STACK_NAME':VPC_STACK_NAME,
                  'CONTAINER_TAG':CONTAINER_TAG,
                  'AWSACCT':AWSACCT,'REGION':awsRegion, 'BUCKET':BUCKET, 'KEYNAME':KEYNAME,
                  'INSTANCE_TYPE':INSTANCE_TYPE }

   
        set_environ(kwargs)
        
        ''' End Setup '''

        ''' App Run '''
        if not check_arn(kwargs): # make sure eksServiceRole exists
            exit(1)
        
        ''' Delete the Cluster '''
        if deleteCluster is True:
            delete_cluster(kwargs)
            sys.exit(0)
        ''' halt the Cluster '''
        if haltCluster is True:
            halt_cluster(kwargs)
            sys.exit(0)            
        ''' Build a Staging Machine (locally) '''
        if buildStaging is True:
            build_staging_machine(kwargs)
        ''' Check if any other tasks to do '''
        if not createCluster and not buildDeployment and \
            not deployCluster and not scaleCluster and not runSmoke:
            print("No other tasks to do -- exiting")
            sys.exit(0)
        ''' Create a Cluster '''
        if createCluster is True:
            create_cluster(kwargs)
        ''' Rest assumes the cluster already exists -- check if it does ... '''
        if not isEKSCluster(clusterName):
            print("No such cluster: %s -- exiting" % clusterName)
            sys.exit(1)
        setKubeconfig(kwargs)
        ''' Check if AWS autoscaling group has been "turned off" '''
        if asgDesiredSize() == 0:
            scale_cluster(kwargs) # turn it on
            wait_for_deployment()
        wait_for_cluster()
        ''' Change to the number of nodes and pods '''
        if scaleCluster:
            dep_running = is_deployment_running()
            scale_cluster(kwargs)
            wait_for_cluster() 
            if dep_running:
                wait_for_deployment()
        ''' Build the master and worker containers '''
        if buildDeployment is True:
            build_deployment(kwargs)
        ''' Deploy the master and worker pods '''
        if deployCluster is True:
            deploy_k8s(kwargs)
            wait_for_deployment()
            ''' Run a smoke test '''
            run_smoke(kwargs)
        elif runSmoke is True:
            run_smoke(kwargs)
        create_setEKSSenv(kwargs)
        print ("# Completed Processing --> Exiting")
        print ("#\tDon't forget to run:\n. ./setEKSSenv.sh")
        
        ''' End App Run '''
        
    except KeyboardInterrupt:
        sys.exit(0)
        
''' Application Functions '''        
def build_staging_machine(kwargs):
    print("Building staging machine")
    cmdstr = ("bash %s ./build_staging_machine.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)   # Need to check for success TODO
    return retcode

def create_cluster(kwargs):
    cn = kwargs['CLUSTER_NAME']
    if isEKSCluster(cn):
        print("Cluster %s already exists -- can't create -- proceeding" % cn)
        return
    nn = str(kwargs['MAXNODES'])
    os.environ['MAXNODES'] = nn
    print("Creating cluster with name: %s and %s nodes" % (cn,nn))
    cmdstr = ("bash %s ./create_eks_cluster.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)    # Need to check for success TODO
    return retcode

def build_deployment(kwargs):
    print("Deploying deployment for %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./build_deployment.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def deploy_k8s(kwargs):
    print("Deploying cluster %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./deploy.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def delete_cluster(kwargs):
    print("Deleting cluster %s" % kwargs['CLUSTER_NAME'])
    cmdstr = ("bash %s ./delete_eks_cluster.sh %s" % (getDBGSTR(), kwargs['CLUSTER_NAME']))
    retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def halt_cluster(kwargs):
    print("Halting cluster %s" % kwargs['CLUSTER_NAME'])
    retcode = None
    ags_name= cmd("aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].AutoScalingGroupName'")
    if ags_name is not None:
        ags_name = ags_name[0]
        cmdstr = ("aws autoscaling set-desired-capacity --auto-scaling-group-name %s --desired-capacity 0" % ags_name)
        retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def run_smoke(kwargs):
    print("Running smoke test on cluster %s" % kwargs['CLUSTER_NAME'])
    get_media(kwargs)
    cmdstr = ("python3 smoketest-v3.py")
    retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def get_media(kwargs):
    example_video_path = 'star_wars_heros.mp4'
    ''' Get the media locally '''
    if not os.path.isfile(example_video_path):
        print("File does not exist: %s" % example_video_path)
        retcode = oscmd("wget https://storage.googleapis.com/scanner-data/tutorial_assets/star_wars_heros.mp4")
    ''' Put the media in AWS bucket '''
    retcode = oscmd("aws s3 ls s3://%s/%s" % (kwargs['BUCKET'],example_video_path))
    if retcode != 0:
        retcode = oscmd("aws s3 cp %s s3://%s" % (example_video_path, kwargs['BUCKET']))

def create_config(configJSON):
    print("Configuration file %s does not exist. You'll now need to create one" % configJSON)
    
    ''' grab the region from the aws config file if it exists '''
    region = "NONE"
    homedir = os.environ['HOME']
    if os.environ['USER'] == 'root' and homedir != '/root':
        homedir = '/root'
    cmdstr = "grep region %s/.aws/config|awk '{print $3}'" % homedir
    retcmd = cmd(cmdstr)
    if retcmd is not None and len(retcmd) > 0:
        region = retcmd[0]
    inputdict = {
        "maxNodes":("INT","Enter maximum number of nodes for the cluster",2 ),
        "nodesDesired":("INT","Enter desired number of nodes for the cluster",2 ),
        "region":("STR","Enter your AWS Region",region ),
        "account":("STR","Enter your AWS Account Number","NONE" ),
        "clusterName":("STR","Enter the cluster name","NONE" ),
        "VPC_STACK_NAME":("STR","Enter your VPC_STACK_NAME","eks-vpc" ),
        "CONTAINER_TAG":("STR","Enter the TAG for your worker container","jpablomch/scanner-aws:latest"),
        "BUCKET":("STR","Enter your AWS Bucket Name for scannerdb","NONE"),
        "KEYNAME":("STR","Enter the name of your AWS SSH KEY","NONE"),
        "INSTANCE_TYPE":("STR","Enter the worker and master instance type","c4.8xlarge")
    }
    fdict = {}
    for key in sorted(inputdict):

        fielddata = inputdict[key]
        ftype = fielddata[0]
        fdefault = str(fielddata[2])
        fprompt = fielddata[1] + " [%s]: " % fdefault

        finput = input(fprompt)
        if not finput:
            fvalue = fdefault
        else:
            fvalue = finput
        if ftype == "INT":
            fvalue = int(fvalue) # catch non integer input TODO
        fdict[key] = fvalue
        pass
    with open(configJSON,'w') as jsonout:
        json.dump(fdict,jsonout, indent = 4, sort_keys = True)
    pass
def scale_cluster(kwargs):
    cmdstr = ("bash %s scalecluster.sh %i" % (getDBGSTR(),kwargs['NODESDESIRED']))
    retcode = oscmd(cmdstr)    # Need to check for success
    pods_on_nodes()    
    return retcode

def scale_deployment(kwargs):
    cmdstr = ("bash %s scaledeployment.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)    # Need to check for success
    pods_on_nodes()
    return retcode
    
def scale_autoscaling_group(kwargs):
    cmdstr = ("bash %s scaleasg.sh %i" % (getDBGSTR(),kwargs['NODESDESIRED']))
    retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

''' kubernetes  functions '''
def wait_for_cluster():
    ''' waits until all nodes are in Ready state '''    
    SETTLETIME = 30 # seconds
    asgDesired = cmd("")
    if not is_cluster_running():    
        while True:
            wait_bar(SLEEPTIME)
            if is_cluster_running():
                break
        wait_bar(SETTLETIME)
    retcode = oscmd('kubectl get nodes')    # Need to check for success
    return retcode

def is_cluster_running():
    ''' checks whether all nodes are in Ready state '''
    oscmd('kubectl get nodes')
    nodessall = int(sp.check_output(
    '''
    kubectl get nodes|grep -v "NAME"|wc|awk '{print $1}'
    ''',
    shell=True).strip().decode('utf-8'))
    if nodessall == 0:
        return False
    nodesrunning = int(sp.check_output(
    '''
    kubectl get nodes|egrep "Ready"|egrep -v "NotReady"|wc|awk '{print $1}'
    ''',
    shell=True).strip().decode('utf-8'))
    if nodessall == nodesrunning:
        return True
    else:
        return False
   
def wait_for_deployment():
    ''' waits until all worker pods are in Running state '''
    SETTLETIME = 120 # seconds
    if not is_deployment_running():
        while True:
            wait_bar(SLEEPTIME)
            if is_deployment_running():
                break            
        wait_bar(SETTLETIME)
    retcode = pods_on_nodes()    # Need to check for success
    return retcode

def is_deployment_running():
    ''' checks whether all worker pods are in Running state '''
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

def setKubeconfig(kwargs):
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

def pods_on_nodes():
    return oscmd("kubectl get pods -o wide|awk '{print $1,$3,\"on node\",$7}'") 

def create_setEKSSenv(kwargs):
    fname = "setEKSSenv.sh"
    filed = open(fname,"w")
    for evar in ['KUBECONFIG', 'LD_LIBRARY_PATH','PATH','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','CLUSTER_NAME']:
        filed.write("export %s=%s\n" % (evar,os.environ[evar]))
    filed.close()

''' AWS Functions '''        
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
    
def isEKSCluster(cname):
    if cname in getEKSClusters():
        cmdstr = ("aws cloudformation describe-stacks|jq -r '.Stacks[] | select(.StackName == \"%s-workers\") | .StackStatus'") % cname
        cmdout = cmd(cmdstr)
        if cmdout is None or cmdout[0] != "CREATE_COMPLETE":
            return False
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

def check_arn(kwargs):
    ''' See if arn exists. If not create '''
    ARN = "arn:aws:iam::%s:role/eksServiceRole" % kwargs['AWSACCT']
    strcmd = "aws iam list-roles|jq -r '.Roles[].Arn'|grep eksServiceRole"
    arn = cmd(strcmd)
    if ARN in arn:
#         print("ARN %s exists" % ARN)
        return True
    ''' ARN does not exist -- create it '''
    print ("ARN %s does not exist. \n\tFrom AWS IAM console, Roles-->Create Role-->EKS-->Permissions-->Next-->Next\n\tName the role 'eksServiceRole'\n\tThis only needs to be done one time for the account" % ARN)
    return False
def asgDesiredSize():
    asgoutput = cmd("aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].DesiredCapacity'")
    if asgoutput is not None:
        return int(asgoutput[0])
    return 0

''' System and application functions '''
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

def set_environ(kwargs):
    # Fix for root with bad home (ubuntu 16.04)
    if kwargs['USER'] == 'root' and kwargs['HOME'] != '/root':
        kwargs['HOME'] = '/root'
        os.environ['HOME'] = '/root'
    getAWScred() 
    for envvar in ['CLUSTER_NAME','AWSACCT','REGION','VPC_STACK_NAME','CONTAINER_TAG','BUCKET','KEYNAME','INSTANCE_TYPE']:
        os.environ[envvar] = kwargs[envvar]
    for envvar in ['NODESDESIRED','MAXNODES']:
        os.environ[envvar] = str(kwargs[envvar])
    # Get paths right
    os.environ['LD_LIBRARY_PATH'] = "/usr/lib:/usr/local/lib" # Scanner needs this
    os.environ['PATH'] = os.environ['PATH'] + ":."
def oscmd(cmdstr):
    return os.system(cmdstr) # return exit status

def cmd(cmdstr):
    output = os.popen(cmdstr).read().split("\n")
    return output

if __name__ == '__main__': main()
