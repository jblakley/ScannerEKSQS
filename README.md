# ScannerEKSQS: The Scanner Elastic Kubernetes Service Quick Start
ScannerEKSQS is a quick start for the ISTC-VCS [Scanner Project](https://github.com/scanner-research/scanner). Its goal is to take  the headache out of deploying scanner in an AWS Kubernetes Cluster. In theory, if you follow the steps below, you will emerge with a working, running instantiation of scanner in your AWS account and will be ready to run your own scale out scanner applications. It makes use of several AWS services including EC2, EBS, S3, CloudFormation, EKS and ECR. The quickstart has been developed for Ubuntu Xenial (16.04). No guarantees or support for other OSs (for now).

## Prerequisites: 

 1. Create an AWS IAM 'eksServiceRole' role if your AWS account does not already have one. From AWS IAM console:

```
Roles-->Create Role-->EKS-->Permissions-->Next-->Next. 
```

Name the role 'eksServiceRole'. Make sure you attach 'AmazonEKSClusterPolicy' and 'AmazonEKSServicePolicy' to the role. This only needs to be done one time for the account. 'eksServiceRole' should be a preconfigured IAM role assuming you have access to EKS services.

 2. Have your AWS account information and credentials at hand.
 
 3. Create a vpc to run your EKS cluster in (if you don't already have one dedicated to that purpose). From an environment for which you have awscli tools installed (version >=1.16. There is a convenience script, awscli_setup.sh, in this repo to setup this version). Note your vpc name -- you will need it later.
 
```
wget https://github.com/jblakley/ScannerEKSQS/raw/master/awscli_setup.sh # If needed
bash awscli_setup.sh # If needed

wget https://github.com/jblakley/ScannerEKSQS/raw/master/create_vpc.sh
bash create_vpc.sh
```

 4. Create an AWS Ubuntu 16.04 instance in your EKS vpc to serve as your scanner client. The instance type is your choice -- a c4.2xlarge w/100GB of EBS storage seems to work well. SSH into that instance and 'sudo -i' to become root. You will likely need to configure your security groups to enable SSH access. Run the rest of the quickstart from that "scanner client" instance.

The basic structure of ScannerEKSQS (and most Scanner EKS deployments) is a staging/client AWS instance, one EKS Master Node and one or more EKS Worker Nodes.

## Running the Quick Start

### Step 1. Building a Staging Machine
Download baseline-ubuntu-16-04.sh and run it. This script assumes that your scanner client is running Ubuntu 16.04. You can get the script with:

```
wget https://github.com/jblakley/ScannerEKSQS/raw/master/baseline-ubuntu-16-04.sh
```

To continue, you must be root. Run:

```
bash baseline-ubuntu-16-04.sh 
```
You will be walked through a series of prompts to configure your environment. You will be prompted for your AWS credentials, your AWS account number, the AWS region, AWS output format (enter 'json'), the VPC to run the cluster in (needs to be the same as your staging machine VPC), an S3 bucket to store the scanner database in, your SSH keyname, the master and worker instance type, a tag for the scanner master and worker container you want to use (use the default unless you know why you're not), the name you want to give the cluster and how many maximum and desired nodes you want in the cluster. 

You can change most of these these values in seb_config.json after the staging machine is setup. Your aws credentials are only stored in the $HOME/.aws/credentials file.

After this, the quickstart will clone this repo into ~/git and build the client into a staging machine. This step takes a while as the quickstart builds scanner and all its dependencies from source.

At the end, your client is a staging machine with the quickstart installed.

```
cd ~/git/ScannerEKSQS
```

### Step 2. Creating, Building and Deploying a Kubernetes cluster and scanner test application
To create a cluster, build the deployment, deploy it and run a smoke test:

```
./scanner_EKS_builder.py --create --build --deploy
```

Each of these steps may be run sequentially. It may go without saying but you can't build and deploy before creating and you can't deploy before building once. Note the quickstart always runs one pod per node so you will have one master node/pod and N-1 worker nodes/pods in your cluster.

### Step 3. Using your cluster
Once you've run the quickstart all the way through, run:

```
. ./setEKSSenv.sh
```

That sets your environment variables and will let you use your EKS Scanner cluster as you normally would.

## Beyond the setup:
Use the scale option to restart a cluster from a halt or to change the number of nodes and pods in your cluster. You can scale the cluster up (to the max nodes set at create time) or down (to 2 -- one node for master and one for a worker):

```
./scanner_EKS_builder.py --scale -n <NODESDESIRED>
```

You can halt your cluster (shut down the master and workers but leave the cluster in place for later restart):

```
./scanner_EKS_builder.py --halt
```

You can delete the cluster with:

```
./scanner_EKS_builder.py --delete
```
Deleting and halting are standalone -- they execute and then exit. 

Complete Command Line Options:

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
