## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root
apt update
apt install python3-pip jq -y
pip3 install tqdm

# Install kubectl
apt-get update && apt-get install -y apt-transport-https
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
touch /etc/apt/sources.list.d/kubernetes.list
echo "deb http://apt.kubernetes.io/ kubernetes-xenial main" | tee -a /etc/apt/sources.list.d/kubernetes.list
apt-get update
apt-get install -y kubectl

QSHOME=~/git/HermesPeak/ScannerPG/EKSScannerQS

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

# Start Container ... TODO
CONTAINER_TAG=$(grep "CONTAINER_TAG" seb_config.json|cut -f 2 -d ":"|sed 's/\"//')
docker pull $CONTAINER_TAG
docker run -it $CONTAINER_TAG bash