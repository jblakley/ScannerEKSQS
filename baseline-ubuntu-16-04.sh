## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root

# AWS Tools
apt update &&
apt-get -y install --upgrade python3-botocore python3-dateutil python3-docutils python3-jmespath python3-roman docutils-common &&
apt -y install awscli &&
aws configure &&
pip3 install awscli --upgrade

# GIT

test -d ~/git || mkdir ~/git
cd ~/git
git clone https://github.com/jblakley/HermesPeak &&
cd ~/git/HermesPeak/ScannerPG/EKSScannerQS &&
echo "Now run build_staging_machine.sh" &&
. ./build_staging_machine.sh

cd ~/git/HermesPeak/ScannerPG/EKSScannerQS
python3 scanner_EKS_builder.py -c jrbk8sQScluster -n 3 -m 5 --create -d 2>&1 |tee create.log