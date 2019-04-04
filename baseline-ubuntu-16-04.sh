#!/usr/bin/env bash
## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root
apt update
apt install python3-pip jq -y
pip3 install tqdm

QSHOME=~/git/ScannerEKSQS

# AWS Tools
apt update &&
apt-get -y install --upgrade python3-botocore python3-dateutil python3-docutils python3-jmespath python3-roman docutils-common &&
apt -y install awscli &&
# your credentials, region and json

apt install python3-pip -y &&
pip3 install awscli --upgrade &&
aws configure &&
aws --version

export AWS_ACCESS_KEY_ID=$(grep aws_access_key_id ~/.aws/credentials|awk '{print $3}')
export AWS_SECRET_ACCESS_KEY=$(grep aws_secret_access_key ~/.aws/credentials|awk '{print $3}')

# GIT

test -d ~/git || mkdir ~/git
cd ~/git
test -d ScannerEKSQS || git clone https://github.com/jblakley/ScannerEKSQS

cd $QSHOME

# AWS Account to create seb configuration
read -p "Enter your AWS account number: " AWS_ACC
# For now, we are using this for max and desired nodes.
read -p "Enter the number of nodes [2]: " NODE_NUM
NODE_NUM=${NODE_NUM:-2}
read -p "Enter your region [us-east-1]: " AWS_REGION
AWS_REGION=${AWS_REGION:-"us-east-1"}
read -p "Enter the name of the cluster : " CLUSTER_NAME
read -p "Enter your S3 bucket: " AWS_BUCKET
read -p "Enter keyname: " KEYNAME

printf "{\n\t\"maxNodes\": ${NODE_NUM},\n\t\"nodesDesired\": ${NODE_NUM},\n\t\"region\":\"${AWS_REGION}\",\n\t\"account\":\"${AWS_ACC}\",\n\t\"clusterName\":\"${CLUSTER_NAME}\",\n\t\"VPC_STACK_NAME\":\"eks-vpc\",\n\t\"CONTAINER_TAG\":\"jpablomch/scanner-aws:latest\",\n\t\"BUCKET\":\"${AWS_BUCKET}\",\n\t\"KEYNAME\":\"${KEYNAME}\"\n}" > seb_config.json

python3 ./scanner_EKS_builder.py --staging
