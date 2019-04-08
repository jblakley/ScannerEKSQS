Prerequisites: 

 1. Create a role for EKS if your AWS account does not have one. From AWS IAM console

```
Roles-->Create Role-->EKS-->Permissions-->Next-->Next. 
```

Name the role 'eksServiceRole'. This only needs to be done one time for the account.

 2. Have your AWS account information and credentials at hand. 

Download baseline-ubuntu-16-04.sh and run it. This script assumes that your staging machine is running Ubuntu 16.04. You can get the script with:

```
wget https://github.com/jblakley/ScannerEKSQS/raw/master/baseline-ubuntu-16-04.sh
```

To continue, you must be root. You will be walked through a series of prompts to configure your environment. You will be prompted for your AWS credentials, your AWS account number, the AWS region, the VPC to run the cluster in (needs to be the same as your staging machine VPC), an S3 bucket to store the scanner database in, your SSH keyname, the master and worker instance type, a tag for the scanner master and worker container you want to use, the name you want to give the cluster and how many maximum and desired nodes you want in the cluster. (Your aws credentials are only stored in the $HOME/.aws/credentials file.)

You can change these values in seb_config.json after the staging machine is setup.


```
bash baseline-ubuntu-16-04.sh 
```

This should clone the repo above into ~/git and builds the instance into a staging machine.

At the end, your machine is a staging machine with the quickstart installed.

```
cd ~/git/ScannerEKSQS
```

To run the quickstart to create a cluster, build the deployment, deploy it and run a smoke test:

```
./scanner_EKS_builder.py --create --build --deploy
```


May go without saying but you can't build and deploy before creating and you can't deploy before building once. Deleting and halting are standalone -- they execute and then exit. Use the scale option to restart a cluster from a stop or to change the number of nodes and pods in your cluster.

Once you've run the quickstart all the way through, run:

```
. ./setEKSSenv.sh
```

That sets your environment variables and will let you use your EKS Scanner cluster as you normally would.

Command Line Options:

```
Usage: scanner_EKS_builder.py [options]

Options:
  -h, --help            show this help message and exit
  -c NAME, --clustername=NAME
                        use NAME as clustername
  -n NODES, --nodesdesired=NODES
                        use NODES as number of desired nodes in the cluster
  -m MAXNODES, --maxnodes=MAXNODES
                        use MAXNODES as number of maximum nodes in the cluster
                        (only on create)
  -i INSTANCE, --instancetype=INSTANCE
                        Use instance type INSTANCE in cluster
  -C, --create          Create the cluster
  -B, --build           Build the deployment for the cluster
  -D, --deploy          Deploy the cluster
  -S, --staging         Make this instance a staging machine
  -G, --scale           Scale the cluster and deployment to specified desired
                        nodes (with -n option)
  -H, --halt            Halt the cluster by changing autoscaling group desired
                        size to 0
  -e, --delete          delete the cluster
  -j FILE.json, --jsonconfig=FILE.json
                        use FILE.json as configuration file
  -d, --debug           Print debugging information
  -v, --verbose         Print detailed information #TODO
```

If something goes wrong, the --debug option is pretty useful.

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
