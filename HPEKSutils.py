#!/usr/bin/env python3
import sys
import os.path

from optparse import OptionParser
import time
import json
import datetime
import shlex, subprocess
from tqdm import tqdm

SLEEPTIME = 10

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
    nodessall = int(cmd0("kubectl get nodes|grep -v 'NAME'|wc|awk '{print $1}'"))
    if nodessall == 0:
        return False
    nodesrunning = int(cmd0("kubectl get nodes|egrep 'Ready'|egrep -v 'NotReady'|wc|awk '{print $1}'"))
    if nodessall == nodesrunning:
        return True
    else:
        return False
   
def wait_for_deployment(podname):
    ''' waits until all pods are in Running state '''
    print("Waiting for all pods to be in Running state and to settle into an operational state ...")
    SETTLETIME = 180 # seconds
    if not is_deployment_running(podname):
        while True:
            wait_bar(SLEEPTIME)
            if is_deployment_running(podname):
                break            
        wait_bar(SETTLETIME)
    retcode = pods_on_nodes()    # Need to check for success
    return retcode

def is_deployment_running(podname):
    ''' checks whether all worker pods are in Running state '''
    oscmd('kubectl get pods -o wide')
    podsall = int(cmd0("kubectl get pods|egrep -e %s|wc|awk '{print $1}'"  % podname))
    podsrunning = int(cmd0('kubectl get pods|egrep -e "%s.*Running"|wc|awk \'{print $1}\'' % podname))
    if podsall == podsrunning:
        return True
    else:
        return False
def newKubeConfig(kwargs):
    kubedir = "%s/.kube" % os.environ['HOME']
    if not os.path.isdir(kubedir):
        os.mkdir(kubedir)
#     confign = os.path.join(kubedir,"config-%s" % kwargs['CLUSTERNAME'])
    confign = os.path.join(kubedir,"config")
    with open("./kubeconfig.template") as templatef:
        templatel = templatef.readlines()
    outlines = []
    for line in templatel:
        tmpline = line.replace("<endpoint-url>",kwargs['ENDPOINT'])\
            .replace("<base64-encoded-ca-cert>",kwargs['CERTIFICATE_AUTH'])\
            .replace("<cluster-name>",kwargs['CLUSTERNAME'])
        outlines.append(tmpline)
        
    with open(confign, 'w') as configf:
        configf.writelines(outlines)
    
    os.environ['KUBECONFIG'] = confign  # Drops old kubeconfig
    kwargs['KUBECONFIG'] = confign
    return confign

def setKubeConfig(kwargs):
    kubedir = "%s/.kube" % os.environ['HOME']
    confign = os.path.join(kubedir,"config-%s" % kwargs['CLUSTERNAME'])
    os.environ['KUBECONFIG'] = confign  # Drops old kubeconfig
    kwargs['KUBECONFIG'] = confign
    return kwargs

def pods_on_nodes():
    return oscmd("kubectl get pods -o wide|awk '{print $1,$3,\"on node\",$7}'") 

def create_setEKSSenv(kwargs):
    fname = "setEKSSparkenv.sh"
    jname = "setEKSSparkenv.json"
    jdict = {}
    with open(fname,"w") as filed:
        for evar in ['KUBECONFIG', 'LD_LIBRARY_PATH','PATH','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','CLUSTERNAME']:
            filed.write("export %s=%s\n" % (evar,os.environ[evar]))
            jdict[evar] = os.environ[evar]
    filed.close()
    with open(jname,'w') as jsonout:
        json.dump(jdict,jsonout, indent = 4, sort_keys = True)
    return fname

''' AWS Functions '''        
def getAWScred(kwargs):
    kwargs['AWS_ACCESS_KEY_ID'] = cmd0('grep aws_access_key_id /root/.aws/credentials|cut -f2 -d "="')
    kwargs['AWS_SECRET_ACCESS_KEY'] = cmd0('grep aws_secret_access_key /root/.aws/credentials|cut -f2 -d "="')
    return kwargs
    
def isEKSCluster(cname):
    if cname in getEKSClusters():
        return True
    else:
        return False
    
def getEKSClusters():
    return cmd("aws eks list-clusters |jq -r '.clusters[]'")

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
    if 'USER' in os.environ and 'HOME' in os.environ and \
        os.environ['USER'] == 'root' and os.environ['HOME'] != '/root':
        os.environ['HOME'] = '/root'
    kwargs = setKubeConfig(kwargs)
    for key in kwargs.keys():
        kwargval = kwargs[key]
        if isinstance(kwargval, (str)):
            os.environ[key] = kwargs[key]
        else:
            os.environ[key] = str(kwargs[key])    
    # Get paths right
    os.environ['LD_LIBRARY_PATH'] = "/usr/lib:/usr/local/lib" # Scanner needs this
    os.environ['PATH'] = os.environ['PATH'] + ":." + ":/root/spark/bin"
    return kwargs

def oscmd(cmdstr):
    ''' Print to console and return exit code '''
    return os.system(cmdstr) # return exit status

def cmd(cmdstr):
    ''' Returns output as a list '''
    output = os.popen(cmdstr).read().split("\n")
    return output

def cmd0(cmdstr):
    ''' Returns the first line of output as a string '''
    retlst = cmd(cmdstr)
    return retlst[0].strip()

def cmd_subp(cmdstr):
    ''' Starts a subprocess to run the cmd and returns subprocess object '''
    args = shlex.split(cmdstr)
    procdata = subprocess.Popen(args)
    return procdata

def humandate(unixtime):
    retstr = datetime.datetime.fromtimestamp(unixtime).strftime('%Y-%m-%d-%H-%M-%S-%f:')
    return retstr


if __name__ == '__main__': main()
