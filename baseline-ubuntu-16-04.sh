## Configure Ubuntu 16.04 Instance AWS for EKS and Scanner
## Must be root

# GIT

test -d ~/git || mkdir ~/git
cd ~/git
git clone https://github.com/jblakley/HermesPeak &&
cd ~/git/HermesPeak/ScannerPG/EKSScannerQS &&
echo "Now run build_staging_machine.sh" &&
. ./build_staging_machine.sh
