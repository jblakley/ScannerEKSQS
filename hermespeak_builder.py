#!/usr/bin/env python3
import sys
import os.path
import shutil
import subprocess as sp
from optparse import OptionParser
import time
import json
import yaml

from tqdm import tqdm

from HPEKSutils import *

SLEEPTIME = 10


def main():
    ''' Default Parameters '''
    VPC_STACK_NAME = "" 
    AWSACCT = ""
    CONFIGFILE = "hpeb_config_new.json"
    
    global debugOn
    global verboseOn

    KEYNAME=""
    
    try:
        print("# Start HermesPeak Builder")
        
        ''' App Setup '''
        parser = OptionParser()
        parser.add_option("-c", "--clustername", dest="clustername",
                      help="use NAME as clustername", metavar="NAME")
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
        kwargs = {}
        with open(configJSON) as jfile:
            kwargs = json.load(jfile)
        
        ''' Only set on command line '''
        verboseOn = options.verbose
        debugOn = options.debug

        buildStaging = options.staging
        createCluster = options.create
        buildDeployment = options.build        
        deployCluster = options.deploy
        deleteCluster = options.delete
        runSmoke = options.smoke

        if options.clustername is not None:
            kwargs['CLUSTERNAME'] = options.clustername
        
        ''' Complete any required options by user input '''
        if not 'CLUSTERNAME' in kwargs:
            kwargs['CLUSTERNAME'] = input("Enter clustername: ")
        ''' assumes AWS credentials are set '''
        kwargs = getAWScred(kwargs)   
        kwargs = set_environ(kwargs)
        
        ''' End Setup '''

        ''' App Run '''
        if not check_arn(kwargs): # make sure eksServiceRole exists
            exit(1)
        
        ''' Delete the Cluster '''
        if deleteCluster is True:
            delete_cluster(kwargs)
            sys.exit(0)

        ''' Check if any other tasks to do '''
        if not createCluster and not buildDeployment and \
            not deployCluster and not runSmoke:
            print("No other tasks to do -- exiting")
            sys.exit(0)
        ''' Create a Cluster '''
        if createCluster is True:
            create_cluster(kwargs)            
            wait_for_cluster()
            connect_efs(kwargs)
        ''' Build the master and worker containers '''
        if buildDeployment is True:
            build_deployment(kwargs)
        ''' Deploy the services '''
        if deployCluster is True:
            deploy(kwargs)

        ''' Run a smoke test '''
        if runSmoke is True:
            run_smoke(kwargs)
#         fname = create_setEKSSenv(kwargs)
        print ("# Completed Processing --> Exiting")
#         print ("#\tDon't forget to run:\n. ./%s" % fname)
        
        ''' End App Run '''
        
    except KeyboardInterrupt:
        sys.exit(0)
        
''' Application Functions '''        
def create_cluster(kwargs):
    cn = kwargs['CLUSTERNAME']
    if isEKSCluster(cn):
        print("Cluster %s already exists -- can't create -- proceeding" % cn)
        setKubeConfig(kwargs)
        return 0
    nodeGroups = kwargs['NodeGroups']
    
    ''' Get the AMI to use for worker nodes '''
    kwargs['AWS_AMI'] = cmd0("aws ec2 describe-images --filters Name='name',Values='EKS-HermesPeakWorker-3'|jq -r '.Images[].ImageId'")
    
    ''' Check the keypair '''
    if not kwargs['KEYNAME'] in cmd0("aws ec2 describe-key-pairs|jq -r '.KeyPairs[] | select(.KeyName == \"%s\") | .KeyName'" % kwargs['KEYNAME']):
        print("invalid Keyname: %s" % kwargs['KEYNAME'])
        return 1
    
    ''' make sure the VPC exists and get VPC_ID '''
    vpcn = kwargs['VPC_STACK_NAME']
    retcode = oscmd("aws cloudformation describe-stacks --stack-name %s >/dev/null" % vpcn)
    if retcode != 0:
        ''' Create the VPC '''
        retcode = oscmd("aws cloudformation create-stack --stack-name %s \
                    --template-body https://amazon-eks.s3-us-west-2.amazonaws.com/1.10.3/2018-06-05/amazon-eks-vpc-sample.yaml" % vpcn)
        oscmd("aws cloudformation wait stack-create-complete --stack-name %s" % vpcn)
    kwargs['VPC_ID'] = cmd0("aws cloudformation describe-stacks --stack-name %s | \
                    jq -r '.Stacks[0].Outputs[] | select(.OutputKey==\"VpcId\") | .OutputValue'" % vpcn)
    
    ''' Get the security groups '''
    kwargs['SECURITY_GROUP_IDS'] = cmd0("aws cloudformation describe-stacks --stack-name %s | \
                    jq -r '.Stacks[0].Outputs[] | select(.OutputKey==\"SecurityGroups\") | .OutputValue'" % vpcn)
 
    ''' Get subnet outputs '''
    kwargs['SUBNET_IDS'] = cmd0("aws cloudformation describe-stacks --stack-name %s | \
                    jq -r '.Stacks[0].Outputs[] | select(.OutputKey==\"SubnetIds\") | .OutputValue'" % vpcn)
    subnettupl = cmd("aws ec2 describe-subnets|jq -r '.Subnets[] | select(.VpcId==\"%s\") | (.AvailabilityZone + \",\" + .SubnetId)'" % kwargs['VPC_ID'])
    del subnettupl[-1] # Last item is null
    kwargs['SUBNET_TUPLE'] = map(lambda x: tuple(x.split(",")), subnettupl )
    
    ''' Get the ARN for the eks service '''
    kwargs['ROLE_ARN'] = "arn:aws:iam::%s:role/eksServiceRole" % kwargs['AWSACCT']


    ''' Create the cluster if it doesn't already exist '''
    yamlfile = "dynamic-hp-eks-cluster.yaml"
    createClusterConfig(kwargs, yamlfile)
    oscmd("eksctl create cluster -f %s" % yamlfile)
    print("EKS cluster created.")
     
    ''' Get cluster endpoint and certificate for configuring kubectl to connect to the cluster '''
    kwargs['ENDPOINT'] = cmd0("aws eks describe-cluster --name %s \
                            --query cluster.endpoint --output text" % cn)
 
    kwargs['CERTIFICATE_AUTH'] = cmd0("aws eks describe-cluster --name %s \
                                   --query cluster.certificateAuthority.data --output text" % cn)    

    ''' Setup kubectl config for connecting to cluster '''
    kwargs['KUBECONFIG'] = newKubeConfig(kwargs)

    ''' Add role binding to allow kube2iam to work correctly See https://github.com/heptio/aws-quickstart/issues/75 '''
    if not cmd0("kubectl get clusterrolebinding kube-system-default-admin -o json|jq -r '.roleRef.apiGroup'"):
        oscmd("kubectl create clusterrolebinding kube-system-default-admin --clusterrole=cluster-admin --serviceaccount=default:default")
    
    ''' Configure Elastic File Service for the cluster '''
    connect_efs(kwargs)

    kwargs = setKubeConfig(kwargs)
    return kwargs

def createClusterConfig(kwargs,fname):
    with open("hp-eks-cluster.yaml.template", 'r') as stream:
        try:
            templated = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    
    templated['metadata']['name'] = kwargs['CLUSTERNAME']
    templated['metadata']['region'] = kwargs['REGION']
    templated['vpc']['id'] = kwargs['VPC_ID']
    
    for ng in kwargs['NodeGroups']:
        if ng['ISON']:
            ngdict = {'name': ng['GROUPNAME'], 
                      'instanceType': ng['INSTANCE_TYPE'],
                      'desiredCapacity': ng['desiredNodes'],
                      'ami':kwargs['AWS_AMI'],
                      'ssh':{'publicKeyName':kwargs['KEYNAME']}}
            templated['nodeGroups'].append(ngdict)
    templated['nodeGroups'].pop(0) # get rid of template nodegroup
    for snt in kwargs['SUBNET_TUPLE']:
        templated['vpc']['subnets']['public'][snt[0]] = {'id':snt[1]}
    templated['vpc']['subnets']['public'].pop('DUMMY') # get rid of template subnet
    
    ''' Write out the yaml '''
    with open(fname, 'w', encoding='utf8') as stream:
        yaml.dump(templated, stream, default_flow_style=False, allow_unicode=True) 

''' one liners '''
def stackstat(stackname):
    return cmd0("aws cloudformation describe-stacks|jq -r '.Stacks[] | select(.StackName == \"%s\") | .StackStatus'" % stackname)

def connect_efs(kwargs):
    print("Connected Elastic File Store")
    cmdstr = ("bash %s ./connect_efs.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)    # Need to check for success TODO
    return retcode

def build_deployment(kwargs):
    print("Deploying deployment for %s" % kwargs['CLUSTERNAME'])
    if 'SCANNERON' in kwargs and kwargs['SCANNERON']:
        print("Building Scanner containers")
        ctag = kwargs['CONTAINER_TAG']
        oscmd('kubectl apply -f scanner-config.yml')  # Just to be safe with updates
        repoexists = oscmd("aws ecr describe-repositories --repository-names scanner >/dev/null")
        if repoexists != 0:
            print("Creating scanner repo")
            oscmd("aws ecr create-repository --repository-name scanner")
        REPO_URI=cmd0("aws ecr describe-repositories --repository-names scanner | jq -r '.repositories[0].repositoryUri'")
        oscmd("docker pull %s" % ctag)
        oscmd('sed "s#<CONTAINER_TAG>#%s#" < Dockerfile.master.template > Dockerfile.master' % ctag)
        oscmd('sed "s#<CONTAINER_TAG>#%s#" < Dockerfile.worker.template > Dockerfile.worker' % ctag)
        oscmd('sed "s#<CONTAINER_TAG>#%s#" < Dockerfile.client.template > Dockerfile.client' % ctag)
        
        oscmd('docker build --no-cache -t %s:scanner-master . -f Dockerfile.master' % REPO_URI)
        oscmd('docker build --no-cache -t %s:scanner-worker . -f Dockerfile.worker' % REPO_URI)
        oscmd('docker build --no-cache -t %s:scanner-client . -f Dockerfile.client' % REPO_URI)        
        oscmd('aws configure set default.region %s' % kwargs['REGION'])
        LOGIN_CMD=cmd0('aws ecr get-login --no-include-email')
ls        oscmd('eval %s' % LOGIN_CMD)
        oscmd('docker push %s:scanner-master' % REPO_URI)
        oscmd('docker push %s:scanner-worker' % REPO_URI)
        oscmd('docker push %s:scanner-client' % REPO_URI)        
        print("Completed Scanner Build")
    if 'SPARKON' in kwargs and kwargs['SPARKON']:
        print("Building Spark Container")
        cmdstr = ("bash %s ./build_deployment.sh" % getDBGSTR())
        retcode = oscmd(cmdstr)    # Need to check for success
        print("Completed Spark Build")
    if 'VDMSON' in kwargs and kwargs['VDMSON']:
        print("Building VDMS Container")
        repoexists = oscmd("aws ecr describe-repositories --repository-names vdms >/dev/null")
        if repoexists != 0:
            print("Creating vdms repo")
            oscmd("aws ecr create-repository --repository-name vdms")        
        oscmd('aws configure set default.region %s' % kwargs['REGION'])
        REPO_URI=cmd0("aws ecr describe-repositories --repository-names vdms | jq -r '.repositories[0].repositoryUri'")
        oscmd('docker build --no-cache -t %s:latest . -f Dockerfile.vdms' % REPO_URI)
        LOGIN_CMD=cmd0('aws ecr get-login --no-include-email')
        oscmd('eval %s' % LOGIN_CMD)        
        oscmd('docker push %s:latest' % REPO_URI)     
        print("Completed VDMS Build")        
    return
def deploy(kwargs):
        cmd("kubectl delete secret aws-storage-key")
        oscmd("kubectl create secret generic aws-storage-key \
                --from-literal=AWS_ACCESS_KEY_ID=%s \
                --from-literal=AWS_SECRET_ACCESS_KEY=%s" % \
                    (kwargs['AWS_ACCESS_KEY_ID'], kwargs['AWS_SECRET_ACCESS_KEY']))
        if 'SCANNERON' in kwargs and kwargs['SCANNERON']:
            deployScanner(kwargs)           
        if 'SPARKON' in kwargs and kwargs['SPARKON']:
            deploySpark(kwargs)
        if 'VDMSON' in kwargs and kwargs['VDMSON']:
            deployVDMS(kwargs)


def deploySpark(kwargs):
    print("Deploying Spark %s" % kwargs['CLUSTERNAME'])
    cmdstr = ("bash %s ./deploySpark.sh" % getDBGSTR())
    retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def deployScanner(kwargs):
    print("Deploying Scanner %s" % kwargs['CLUSTERNAME'])
    
    if 'DBTYPE' in kwargs:
        dbtype = kwargs['DBTYPE']
        if not dbtype in ['EFS','S3']:
            print("Invalid db storage type: %s, assuming S3" % dbtype)
            dbtype = 'S3'
    else:
        print ("No db storage type specified, assuming S3")
        dbtype = "S3"
    oscmd("kubectl delete -f scanner-config.yml")    # May error if doesn't exist
    configyml = 'scanner-config.yaml.template.' + dbtype
    configtoml = 'config.toml.template.' + dbtype
    REPO_URI=cmd0("aws ecr describe-repositories --repository-names scanner | jq -r '.repositories[0].repositoryUri'")
    oscmd("sed \"s|<BUCKET>|%s|g;s|<REGION>|%s|g\" %s > scanner-config.yml" % (kwargs['BUCKET'],kwargs['REGION'],configyml))
    oscmd("sed \"s|<BUCKET>|%s|g;s|<REGION>|%s|g\" %s > config.toml" % (kwargs['BUCKET'],kwargs['REGION'], configtoml))
    oscmd("kubectl apply -f scanner-config.yml")
    
    REPLICAS = int(cmd0("kubectl get nodes -o json|jq -r '.items[].metadata.labels | select(.\"%s\" == \"Scanner\") | .\"%s\"'|wc|awk \'{print $1}\'" % (kwargs['NODEGROUP_LABEL'],kwargs['NODEGROUP_LABEL'])))
    REPLICAS -= 1
    
    oscmd('sed "s|<REPO_NAME>|%s:scanner-master|g;s|<AWSACCT>|%s|g" master.yml.template > master.yml' % (REPO_URI,kwargs['AWSACCT']))
    oscmd('sed "s|<REPO_NAME>|%s:scanner-worker|g;s|<AWSACCT>|%s|g" worker.yml.template > worker.yml' % (REPO_URI,kwargs['AWSACCT']))

    cmd('kubectl delete service scanner-master 2>/dev/null')
    cmd('kubectl delete -f master.yml 2>/dev/null')
    cmd('kubectl delete -f worker.yml 2>/dev/null') 
    oscmd('kubectl create -f master.yml')
    oscmd('kubectl create -f worker.yml') 
    oscmd('kubectl scale deployment/scanner-worker --replicas=%i' % REPLICAS)
    
    ''' Expose the master port for the workers to connect to ''' 
    retcode = oscmd("kubectl expose -f master.yml --type=LoadBalancer --target-port=8080 --selector='app=scanner-master'")
    wait_for_deployment("worker")
    return retcode

def deployVDMS(kwargs):
    print("Deploying VDMS %s" % kwargs['CLUSTERNAME'])
    REPO_URI=cmd0("aws ecr describe-repositories --repository-names vdms | jq -r '.repositories[0].repositoryUri'")
    cmd('kubectl delete service vdms 2>/dev/null')
    cmd('kubectl delete -f vdms.yml 2>/dev/null')
    oscmd('kubectl create -f vdms.yml')
    REPLICAS = int(cmd0("kubectl get nodes -o json|jq -r '.items[].metadata.labels | select(.\"%s\" == \"Vdms\") | .\"%s\"'|wc|awk \'{print $1}\'" % (kwargs['NODEGROUP_LABEL'],kwargs['NODEGROUP_LABEL'])))

    oscmd('kubectl scale deployment/vdms --replicas=%i' % REPLICAS)
    
    ''' Expose the master port for the workers to connect to ''' 
    retcode = oscmd("kubectl expose -f vdms.yml --type=LoadBalancer --target-port=55555 --selector='app=vdms'")
    wait_for_deployment("vdms")
    return retcode
        
    
def delete_cluster(kwargs):
    cn = kwargs['CLUSTERNAME']
    print("Deleting cluster %s" % cn)

    ''' Delete node groups '''
    for cl in active_clusters(cn):
        if not "cluster" in cl:
            oscmd("aws cloudformation delete-stack --stack-name %s" % cl)
    
    ''' Wait for node groups to be deleted '''
    for cl in active_clusters(cn):
        if not "cluster" in cl:
            while delete_inprogress(cl):
                print("Delete in Progress: Cluster %s" % cl)
                time.sleep(3)

    ''' Delete the cluster '''
    for cl in active_clusters(cn):
        oscmd("aws cloudformation delete-stack --stack-name %s" % cl)
        while delete_inprogress(cl):
            print("Delete in Progress: Cluster %s" % cl)
            time.sleep(3)
    print("Cluster %s delete" % cn)
    return
def active_clusters(cn):
    return filter(None,cmd("aws cloudformation describe-stacks|jq -r '.Stacks[] | select(.StackName | contains(\"%s\")) | .StackName'" % cn))

def delete_inprogress(cn):
    deletelst = list(filter(None,cmd("aws cloudformation describe-stacks|jq -r '.Stacks[] | \
        select(.StackName | contains(\"%s\")) | select(.StackStatus == \"DELETE_IN_PROGRESS\")'" % cn)))
    if len(deletelst) <1:
        return False
    else:
        return True

def halt_cluster(kwargs):
    print("Halting cluster %s" % kwargs['CLUSTERNAME'])
    retcode = None
    ags_name= cmd("aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].AutoScalingGroupName'")
    if ags_name is not None:
        ags_name = ags_name[0]
        cmdstr = ("aws autoscaling set-desired-capacity --auto-scaling-group-name %s --desired-capacity 0" % ags_name)
        retcode = oscmd(cmdstr)    # Need to check for success
    return retcode

def run_smoke(kwargs):
    print("Running smoke test on cluster %s" % kwargs['CLUSTERNAME'])
    if kwargs['SCANNERON']:
        get_media(kwargs)
        cmdstr = ("python3 smokescanner-v4.py")
        retcode = oscmd(cmdstr)    # Need to check for success
    return

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

''' one liners '''
def stackstat(stackname):
    return cmd0("aws cloudformation describe-stacks|jq -r '.Stacks[] | select(.StackName == \"%s\") | .StackStatus'" % stackname)

def getDBGSTR():
    if debugOn:
        return "-vx"
    else:
        return ""

if __name__ == '__main__': main()
