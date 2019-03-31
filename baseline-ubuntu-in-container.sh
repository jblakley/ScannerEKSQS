## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root
apt update
apt install python3-pip jq -y
pip3 install tqdm

test -z "$1" && export CLUSTER_NAME=jrbk8sQScluster # DEFAULT
test -n "$1" && export CLUSTER_NAME=$1 # OVERRIDE

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

# Install heptio auth
curl -o heptio-authenticator-aws https://amazon-eks.s3-us-west-2.amazonaws.com/1.10.3/2018-06-05/bin/linux/amd64/heptio-authenticator-aws
chmod +x ./heptio-authenticator-aws
mkdir -p ~/bin
cp heptio-authenticator-aws ~/bin
echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc
export PATH=$HOME/bin:$PATH

# Install kubectl
apt-get update && apt-get install -y apt-transport-https
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
touch /etc/apt/sources.list.d/kubernetes.list
echo "deb http://apt.kubernetes.io/ kubernetes-xenial main" | tee -a /etc/apt/sources.list.d/kubernetes.list
apt-get update
apt-get install -y kubectl

cd $QSHOME
