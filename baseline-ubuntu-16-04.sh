## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root
test -z "$1" CLUSTER_NAME=jrbk8sQScluster # DEFAULT
test -n "$1" CLUSTER_NAME=$1
QSHOME=~/git/HermesPeak/ScannerPG/EKSScannerQS

DESIRENODES=2
MAXNODES=2



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
git clone https://github.com/jblakley/HermesPeak


cd $QSHOME &&
echo "Now run build_staging_machine.sh" &&
. ./build_staging_machine.sh &&

cd $QSHOME &&
python3 scanner_EKS_builder.py -c $CLUSTER_NAME -n 2 -m 2 --create --deploy && 
. ./setkubectl.sh
