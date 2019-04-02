Prerequisites: 

 1. Create a role for EKS if your AWS account does not have one. From AWS IAM console

```
Roles-->Create Role-->EKS-->Permissions-->Next-->Next. 
```

Name the role 'eksServiceRole'. This only needs to be done one time for the account.

 2. Have your AWS account information and credentials at hand. 

From http://github.com/jblakley/HermesPeak/ScannerPG/EKSScannerQS
Run the following on your brand new Ubuntu 16.04 instance. Download the file and run it. You don't need to clone but OK if you do.
You will need your AWS credentials. You must be root.

```
bash baseline-ubuntu-16-04.sh 
```

This should clone the repo above into ~/git and builds the instance into a staging machine.

At the end, your machine is a staging machine with the quickstart installed.

```
cd ~/git/HermesPeak/ScannerPG/EKSScannerQS # you may already be here at the end of your build
```

To run the quickstart to create a cluster, build the deployment, deploy it and run a smoke test:

```
python3 scanner_EKS_builder.py -c <CLUSTER_NAME> --create --build --deploy
```

```
Usage: scanner_EKS_builder.py [options]
Options:
  -h, --help            show this help message and exit
  -c NAME, --clustername=NAME
                        use NAME as clustername
  -n INT, --nodesdesired=INT
                        use INT as number of desired nodes in the cluster
  -m INT, --maxnodes=INT
                        use INT as number of maximum nodes in the cluster 
  -C, --create          Create the cluster
  -B, --build           Build the deployment for the cluster
  -D, --deploy          Build and Deploy the cluster
  -S, --staging         Make this instance a staging machine
  -e, --delete          delete the cluster
  -j NAME, --jsonconfig=NAME
                        use NAME as json configuration file
  -d, --debug           Print debugging information
  -v, --verbose         Print detailed information #TODO
```
If something goes wrong, the --debug option is pretty useful.

May go without saying but you can't build and deploy before creating and you can't deploy before building once.

Once you've run the quickstart all the way through, run:

```
. ./setk8SSenv.sh
```

That will let you use your EKS Scanner cluster as you normally would.


The configuration file supports the following options:

```
{
	"maxNodes":<INT -- maximum number of nodes for the EKS cluster>,
	"nodesDesired":<INT -- desired number of nodes for the EKS cluster>,
	"region":"<AWS Region>",
	"account":"<AWS Account Number>",
	"clusterName":"<Name for the cluster>",
	"VPC_STACK_NAME":"<VPC of the staging machine>",
	"CONTAINER_TAG":"<Container Tag>",
	"BUCKET":"<AWS Bucket Name for ScannerDB and other>"
	"INSTANCE_TYPE":<AWS instance type for master and worker nodes>"
	"KEYNAME":"<Name of AWS SSH Key>"
}
```
