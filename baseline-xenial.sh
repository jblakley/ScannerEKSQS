#!/usr/bin/env bash
## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root
apt update

# Pyhon 3.6, 3.7
#apt install software-properties-common -y && add-apt-repository ppa:deadsnakes/ppa -y
#apt update && apt install python3.5 -y && update-alternatives --install /usr/bin/python3 python /usr/bin/python3.6 1

## Python 3.5.8 -- from source
#apt install -y build-essential checkinstall &&
#apt install -y libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev
#apt remove python3
#wget https://www.python.org/ftp/python/3.5.8/Python-3.5.8rc1.tgz
#tar xvzf Python-3.5.8rc1.tgz
#cd Python-3.5.8rc1
#./configure && make && make install

apt update
apt install python3-pip jq git -y
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
python3 ./hermespeak_builder.py --staging
