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
read -p "Clone the dev branch? [Y/n]: " DEVBRANCH
if [ "$DEVBRANCH" == "Y" ]
then
	BRANCH=dev
else
	BRANCH=master
fi

test -d ~/git || mkdir ~/git
cd ~/git

test -d ScannerEKSQS || git clone -b $BRANCH https://github.com/jblakley/ScannerEKSQS

cd $QSHOME

python3 ./scanner_EKS_builder.py --staging
