#!/usr/bin/env python3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np

import os.path
import subprocess
import shutil
import time, datetime
import shlex

def main():
    
    kwargs = {}
    os.environ['KUBECONFIG'] = cmd0("ls -tr /root/.kube/config*|tail -1")
    os.environ['PATH'] = os.environ['PATH'] + ":." + ":/root/spark/bin"
    os.environ['AWS_ACCESS_KEY_ID'] = cmd0('grep aws_access_key_id /root/.aws/credentials|cut -f2 -d "="')
    os.environ['AWS_SECRET_ACCESS_KEY'] = cmd0('grep aws_secret_access_key /root/.aws/credentials|cut -f2 -d "="')
    os.environ['AWS_DEFAULT_REGION']  = cmd0('grep region /root/.aws/config|cut -f2 -d "="')
    CLUSTERNAME=cmd0("kubectl get nodes -o json|grep cluster-name|sort|uniq|awk '{print $2}'").replace("\"","").replace(",","")
    ENDPOINT=cmd0("aws eks describe-cluster --name %s | jq -r '.cluster.endpoint'" % CLUSTERNAME)
    NODEGROUP_LABEL="alpha.eksctl.io/nodegroup-name"

   
    CVERSION=130
    oscmd("aws ecr describe-repositories --repository-names spark | jq -r '.repositories[0].repositoryUri'") 
    REPO_URI= cmd0("aws ecr describe-repositories --repository-names spark | jq -r '.repositories[0].repositoryUri'") 
    CONTAINERTAG = "%s:V%i" % (REPO_URI,CVERSION)
#     LOGIN_CMD=cmd0('aws ecr get-login --no-include-email')
#     oscmd('eval %s' % LOGIN_CMD)        
#     oscmd("docker pull %s" % CONTAINERTAG)    

    scmd = "spark-submit \
            --master k8s://%s \
            --deploy-mode cluster \
            --name spark-pi \
            --conf spark.executor.instances=1 \
            --conf spark.kubernetes.container.image=%s \
            --conf spark.kubernetes.node.selector.%s=Spark \
            local:///opt/spark/QSexamples/pi.py" %(ENDPOINT,CONTAINERTAG,NODEGROUP_LABEL)

#     scmd = "spark-submit \
#             --deploy-mode client \
#             --name spark-pi \
#             local:///root/spark/QSexamples/pi.py"             
    oscmd(scmd)
    
def oscmd(cmdstr): # Prints out to console and returns exit status
    return os.system(cmdstr)

def cmd(cmdstr): # Returns the output of the command as a list
    output = os.popen(cmdstr).read().split("\n")
    return output

def cmd0(cmdstr): # Returns first line of output as a string
    retlst = cmd(cmdstr)
    return retlst[0].strip()

def cmds(cmdstr): # Returns all output  of the command as a string
    output = os.popen(cmdstr).read()
    return output

def cmd_subp(cmdstr):
    args = shlex.split(cmdstr)
    procdata = subprocess.Popen(args)
    return procdata

def humandate(unixtime):
    retstr = datetime.datetime.fromtimestamp(unixtime).strftime('%Y-%m-%d-%H-%M-%S-%f')
    return retstr    
if __name__ == '__main__': main()
    