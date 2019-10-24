#!/usr/bin/env python3
import sys
import os.path
import shutil
import subprocess as sp
from optparse import OptionParser
import time
import json
import yaml

from HPEKSutils import *
from awscli.customizations.emr.constants import FALSE


SLEEPTIME = 10


def main():
    ''' Default Parameters '''
    CONFIGFILE = "hpeb_config_new.json"
    global debugOn
    global verboseOn
    origdir = os.getcwd()
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
        parser.add_option("-T", "--smoke",
                      action="store_true", dest="smoke", default=False,
                      help="Try out your cluster by running a smoke test")
        parser.add_option("-R", "--remount",
                      action="store_true", dest="remount", default=False,
                      help="Remount EFS")
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
        
#         if not os.path.isfile(configJSON):
#             create_config(configJSON)
        kwargs = {}
        with open(configJSON) as jfile:
            kwargs = json.load(jfile)
        
        ''' Set high level switches for convenience '''
        for ng in kwargs['NodeGroups']:
            if ng['GROUPNAME'] == 'Scanner':
                kwargs['SCANNERON'] = ng['ISON']
            elif ng['GROUPNAME'] == 'Vdms':
                kwargs['VDMSON'] = ng['ISON']

        ''' Only set on command line '''
        verboseOn = options.verbose
        debugOn = options.debug

        buildStaging = options.staging
        createCluster = options.create
        buildDeployment = options.build        
        deployCluster = options.deploy
        deleteCluster = options.delete
        runSmoke = options.smoke
        remountEFS = options.remount

        if options.clustername is not None:
            kwargs['CLUSTERNAME'] = options.clustername
        
        ''' Complete any required options by user input '''
        if not 'CLUSTERNAME' in kwargs:
            kwargs['CLUSTERNAME'] = input("Enter clustername: ")
        
        ''' Basic Configuration '''
        if buildStaging:
            build_staging(kwargs)
        os.chdir(origdir)
            
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
        if not createCluster and not buildDeployment and not buildStaging and \
            not deployCluster and not runSmoke and not remountEFS:
            print("No other tasks to do -- exiting")
            sys.exit(0)
        ''' Install Scanner '''
        if buildStaging:
            installScanner(kwargs)
            os.chdir(origdir)
            oscmd("banner run local smoke test")  
            runPyProg("smokescanner-local-v1.py")
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
        ''' Remount EFS '''
        if remountEFS:
            remount_EFS(kwargs)
        ''' Run a smoke test '''
        if runSmoke is True:
            run_smoke(kwargs)
        print ("# Completed Processing --> Exiting")
        
        ''' End App Run '''
        
    except KeyboardInterrupt:
        sys.exit(0)

''' Application Functions '''
def runTest(kwargs):
    connect_efs(kwargs)
    
    sys.exit(0)
def build_staging(kwargs):
    ''' Upfront configure '''
    if not 'USER' in os.environ:
        os.environ['USER'] = "root"
    if not 'HOME' in os.environ:
        os.environ['HOME'] = "/root"
   
    ''' General installs '''
    aptlst  = ['sysvbanner','vim','jq','python3-pip','apt-transport-https','ca-certificates curl',
               'software-properties-common','x265','libx265-dev','nfs-common']
    piplst = ['numpy','tqdm','tensorflow','align','pandas','vdms']
    aptUpdate()
    aptInstall(aptlst,"")
    pipInstall(piplst,"")
    
    oscmd("banner build staging machine")
    ''' Docker '''
    oscmd("curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -")
    rel = cmd0("lsb_release -cs")
    oscmd("add-apt-repository 'deb [arch=amd64] https://download.docker.com/linux/ubuntu %s stable'" % rel)
    aptUpdate()
    aptInstall(['docker-ce'],"")    
    oscmd("usermod -a -G docker %s" % os.environ['USER'])
    
    ''' Upgrade awscli '''
    pipInstall(['awscli'],"--upgrade --user")
    
    ''' Install Kubectl '''
    if not os.path.isfile("/etc/apt/sources.list.d/kubernetes.list"):
        oscmd("curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -")
        oscmd("touch /etc/apt/sources.list.d/kubernetes.list")
        oscmd("echo \"deb http://apt.kubernetes.io/ kubernetes-xenial main\" | tee -a /etc/apt/sources.list.d/kubernetes.list")
    aptUpdate()
    aptInstall(['kubectl'],"")

    ''' Install heptio auth '''
    heptauth =  "heptio-authenticator-aws"
    oscmd("curl -o %s https://amazon-eks.s3-us-west-2.amazonaws.com/1.10.3/2018-06-05/bin/linux/amd64/%s" % (heptauth,heptauth))
    oscmd("chmod +x %s" % heptauth)
    bindir = os.path.join(os.environ['HOME'],"bin")
    if not os.path.isdir(bindir):
        os.mkdir(bindir)
    heptauthdst = os.path.join(bindir,heptauth)
    if not os.path.isfile(heptauthdst):
        shutil.copy2(heptauth,heptauthdst)

    ''' Configure paths in bashrc and in os.environ '''
    bashrcpath = os.path.join(os.environ['HOME'],".bashrc")
    oscmd("echo 'export PATH=$HOME/bin:.:$PATH' >> %s" % bashrcpath)
    os.environ['PATH'] = os.environ['PATH'] + ":" + bindir
    
    ''' EKSCTL '''
    oscmd("curl --silent --location \"https://github.com/weaveworks/eksctl/releases/download/latest_release/eksctl_$(uname -s)_amd64.tar.gz\" | tar xz -C /tmp")
    oscmd("mv /tmp/eksctl /usr/local/bin && eksctl version")
    
def installScanner(kwargs):
    oscmd("banner install scanner")
    ''' Dependencies '''
    deplist = ["build-essential",
        "cmake","git","libgtk2.0-dev","pkg-config","unzip","llvm-5.0-dev","clang-5.0","libc++-dev",
        "libgflags-dev","libgtest-dev","libssl-dev","libcurl3-dev","liblzma-dev",
        "libeigen3-dev","libgoogle-glog-dev","libatlas-base-dev","libsuitesparse-dev",
        "libgflags-dev","libx264-dev","libopenjpeg-dev","libxvidcore-dev",
        "libpng-dev","libjpeg-dev","libbz2-dev","wget",
        "libleveldb-dev","libsnappy-dev","libhdf5-serial-dev","liblmdb-dev","python-dev",
        "python-tk","autoconf","autogen","libtool","libtbb-dev","libopenblas-dev",\
        "liblapacke-dev","swig","yasm","python3.5","python3-pip","cpio","automake","libass-dev",
        "libfreetype6-dev","libsdl2-dev","libtheora-dev","libtool",
        "libva-dev","libvdpau-dev","libvorbis-dev","libxcb1-dev","libxcb-shm0-dev",
        "libxcb-xfixes0-dev","mercurial","texinfo","zlib1g-dev","curl","libcap-dev",
        "libboost-all-dev","libgnutls-dev","libpq-dev","postgresql"]
    aptInstall(deplist,"")
    
    ''' Build Dependencies and Scanner '''
    scannerhome = "/opt/scanner"
    if not os.path.isdir(scannerhome):
        oscmd("git clone https://github.com/scanner-research/scanner %s" % scannerhome)
    os.chdir(scannerhome)
#     GITVERSION="820f85a082a9a5436e35c7986bb917ee0267e0b1"
#     oscmd("git checkout %s" % GITVERSION)    
    oscmd("bash ./deps.sh -a --prefix /usr/local")
    if not os.path.isdir("build"):
        os.mkdir("build")
    os.chdir("build")
    nproc = cmd0("nproc")
    oscmd("cmake .. && make -j%s" % nproc)

    ''' Build and install scannerpy '''
    os.chdir(scannerhome)
    oscmd("bash ./build.sh")
    
    ''' Install ScannerTools '''
    installScannerTools(kwargs)
    
    ''' Build Special Scanner Operators '''
    buildScannerOperators(kwargs)
    
    ''' Final cleanups '''
    oscmd("chmod +x /usr/local/lib/libstorehouse.so")
    os.environ['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH'] + ':/usr/local/lib'
    oscmd("echo export LD_LIBRARY_PATH=%s >> %s" % (os.environ['LD_LIBRARY_PATH'],
                                             os.path.join(os.environ['HOME'],".bashrc")))

def installScannerTools(kwargs):
    oscmd("banner install scanner tools")
    scannertools = "/opt/scannertools"
    if not os.path.isdir(scannertools):
        oscmd("git clone https://github.com/scanner-research/scannertools %s" % scannertools)
    os.chdir(scannertools)    
    toollst = ['scannertools_infra','scannertools','scannertools_caffe']
    for tool in toollst:
        os.chdir(tool)
        pipInstall(['.'], "--user -e .")
        os.chdir('..')
def buildScannerOperators(kwargs):
    ''' Resize '''
    oscmd("banner build scanner ops")    
    reszdir = "/opt/scanner/examples/tutorials/resize_op/"
    nproc = cmd0("nproc")
    curdir = os.getcwd()
    
    os.chdir(reszdir)
    oscmd("cmake . && make -j%s" % nproc)
    os.chdir(curdir)
    
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

def connect_efs(kwargs):
    print("Connecting Elastic File Store")
 
    REGION = kwargs['REGION']
    EFSVOL = cmd0("aws efs describe-file-systems|jq -r '.FileSystems[].FileSystemId'")
    ''' Start the provisioner '''
    oscmd("kubectl apply -f efs-manifest.yaml")
    ''' Wait for efs-provisioner '''
    running = False
    while not running:
        if oscmd("kubectl get pods|egrep '^efs.*Running'") == 0:
            break
        time.sleep(SLEEPTIME)
    while not running:
        if oscmd("kubectl get pv -o json|jq -r '.items[].metadata.name'") == 0:
            break
        time.sleep(SLEEPTIME)
#     EFSPVNAME=cmd0("kubectl get pv -o json|jq -r '.items[].metadata.name'")
    EFSPVNAME=cmd0("kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == \"efs\") | .spec.volumeName'")
    SDBPVNAME=cmd0("kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == \"efs-sdb\") | .spec.volumeName'")
    oscmd("kubectl patch pv %s -p '{\"spec\":{\"persistentVolumeReclaimPolicy\":\"Retain\"}}'" % EFSPVNAME)
    oscmd("kubectl patch pv %s -p '{\"spec\":{\"persistentVolumeReclaimPolicy\":\"Retain\"}}'" % SDBPVNAME)
    dlist = [("/","/efs"),("/efs-"+ EFSPVNAME,"/efsc"),
             ("/efs-sdb-"+ SDBPVNAME, "/efs-sdb"),
             ("/efs-sdb-"+ SDBPVNAME, "/root/.scanner")  ]
    [os.mkdir(dname[1]) for dname in dlist if not os.path.isdir(dname[1])]    
    
    for mp in dlist:
        if oscmd("mountpoint -q %s" % mp[1]) != 0:
            mount_efsdrive(EFSVOL, REGION, mp[0],mp[1])

    return

def remount_EFS(kwargs):
    REGION = kwargs['REGION']
    EFSVOL = cmd0("aws efs describe-file-systems|jq -r '.FileSystems[].FileSystemId'")
    EFSPVNAME=cmd0("kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == \"efs\") | .spec.volumeName'")
    SDBPVNAME=cmd0("kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == \"efs-sdb\") | .spec.volumeName'")

    dlist = [("/","/efs"),("/efs-"+ EFSPVNAME,"/efsc"),
             ("/efs-sdb-"+ SDBPVNAME, "/efs-sdb"),
             ("/efs-sdb-"+ SDBPVNAME, "/root/.scanner")  ]
    
    for mp in dlist:
        if oscmd("mountpoint -q %s" % mp[1]) == 0:
            oscmd("umount %s" % mp[1])
        mount_efsdrive(EFSVOL, REGION, mp[0],mp[1])
    
def mount_efsdrive(vol,reg,rt, mp):
    oscmd(" mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport %s.efs.%s.amazonaws.com:%s %s" % (vol, reg, rt, mp))

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
        oscmd('eval %s' % LOGIN_CMD)
        oscmd('docker push %s:scanner-master' % REPO_URI)
        oscmd('docker push %s:scanner-worker' % REPO_URI)
        oscmd('docker push %s:scanner-client' % REPO_URI)        
        print("Completed Scanner Build")
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
    if 'VDMSON' in kwargs and kwargs['VDMSON']:
        deployVDMS(kwargs)
    wait_for_deployment("worker")

def deployScanner(kwargs):
    print("Deploying Scanner %s" % kwargs['CLUSTERNAME'])
    
    if 'DBTYPE' in kwargs:
        dbtype = kwargs['DBTYPE']
        if not dbtype in ['EFS','S3']:
            print("Invalid db storage type: %s, assuming EFS" % dbtype)
            dbtype = 'EFS'
    else:
        print ("No db storage type specified, assuming EFS")
        dbtype = "EFS"
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
#     wait_for_deployment("worker")
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
        runPyProg("smokescanner-cluster-v1.py")
    if kwargs['SCANNERON']:
        runPyProg("smokevdms-v1.py")
    return

def get_media(kwargs):
    example_video_path = 'star_wars_heros.mp4'
    ''' Get the media locally '''
    if not os.path.isfile(example_video_path):
        print("File does not exist: %s" % example_video_path)
        oscmd("wget https://storage.googleapis.com/scanner-data/tutorial_assets/star_wars_heros.mp4")

''' one liners '''
def stackstat(stackname):
    return cmd0("aws cloudformation describe-stacks|jq -r '.Stacks[] | select(.StackName == \"%s\") | .StackStatus'" % stackname)
def aptUpdate():
    oscmd("apt update")
def aptInstall(lst,args):
    oscmd("apt install -y %s %s" % (args,' '.join(lst)))
def pipInstall(lst,args):
    oscmd("pip3 install %s %s" % (args,' '.join(lst)))
def runPyProg(progn):
    oscmd("python3 ./%s" % progn)

def getDBGSTR():
    if debugOn:
        return "-vx"
    else:
        return ""

if __name__ == '__main__': main()
