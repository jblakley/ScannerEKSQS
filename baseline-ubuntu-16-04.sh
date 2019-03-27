## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root
apt install python3-pip
pip3 install tqdm

test -z "$1" && export CLUSTER_NAME=jrbk8sQScluster # DEFAULT
test -n "$1" && export CLUSTER_NAME=$1 # OVERRIDE

QSHOME=~/git/HermesPeak/ScannerPG/EKSScannerQS

DESIRENODES=2
MAXNODES=2
echo CLUSTER_NAME=$CLUSTER_NAME

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
test -d HermesPeak || git clone https://github.com/jblakley/HermesPeak

cd $QSHOME
python3 ./scanner_EKS_builder.py -n $DESIRENODES -m $MAXNODES -c $CLUSTER_NAME --staging
