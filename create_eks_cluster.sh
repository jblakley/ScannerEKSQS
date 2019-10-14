#!/bin/bash

programname=$0

function errorexit {
    echo "$programname EXITING: $*"
    exit 1
}

# Set up parameters -- if not set in environment, prompt to get them TODO

test -z "$AMI" && export AMI=$(aws ec2 describe-images --filters Name='name',Values='EKS-HermesPeakWorker-3'|jq -r '.Images[].ImageId')

for envvar in "VPC_STACK_NAME" "AWSACCT" "INSTANCE_TYPE" "MAXNODES" "NODESDESIRED" "AMI" "KEYNAME" "BUCKET" "REGION"
do
	test -z ${!envvar} && errorexit "${envvar} is not set"
done

# CHECK THE CLUSTER PARAMETERS ARE VALID
# CHECK THE KEYNAME
ISKEYNAME=$(aws ec2 describe-key-pairs|jq -r ".KeyPairs[] | select(.KeyName == \"$KEYNAME\") | .KeyName")
test -z "$ISKEYNAME" && errorexit "Invalid KEYNAME $KEYNAME"


# CHECK THE BUCKET
BUCKETSTATUS=$(aws s3api head-bucket --bucket $BUCKET 2>&1)
test -n "$BUCKETSTATUS" && errorexit "Invalid BUCKET: $BUCKET"

export PATH=$PATH:.

### 1. Create a VPC (virtual private cloud) to launch the cluster into
aws cloudformation describe-stacks --stack-name $VPC_STACK_NAME
VPC_EXISTS=$?
if [ $VPC_EXISTS -ne 0 ]; then
    aws cloudformation create-stack --stack-name $VPC_STACK_NAME \
        --template-body https://amazon-eks.s3-us-west-2.amazonaws.com/1.10.3/2018-06-05/amazon-eks-vpc-sample.yaml
fi

# Wait for stack to create
aws cloudformation wait stack-create-complete --stack-name $VPC_STACK_NAME

# Get VPC ID
VPC_ID=$(aws cloudformation describe-stacks --stack-name $VPC_STACK_NAME \
             | jq -r '.Stacks[0].Outputs[] | select(.OutputKey=="VpcId") | .OutputValue')

# Get security group ids
SECURITY_GROUP_IDS=$(aws cloudformation describe-stacks --stack-name $VPC_STACK_NAME \
                         | jq -r '.Stacks[0].Outputs[] | select(.OutputKey=="SecurityGroups") | .OutputValue')

# Get subnet outputs
SUBNET_IDS=$(aws cloudformation describe-stacks --stack-name $VPC_STACK_NAME \
                 | jq -r '.Stacks[0].Outputs[] | select(.OutputKey=="SubnetIds") | .OutputValue')

### 2. Create the EKS cluster
ROLE_ARN=arn:aws:iam::${AWSACCT}:role/eksServiceRole

aws eks create-cluster --name $CLUSTER_NAME \
    --role-arn $ROLE_ARN \
    --resources-vpc-config subnetIds=$SUBNET_IDS,securityGroupIds=$SECURITY_GROUP_IDS

# Wait for cluster to be created...
echo "Waiting for EKS cluster to be created... (may take a while)"
COND=$(aws eks describe-cluster --name $CLUSTER_NAME --query cluster.status)
while ! [ "$COND" = "\"ACTIVE\"" ]; do
  sleep 20
  COND=$(aws eks describe-cluster --name $CLUSTER_NAME --query cluster.status)
  echo "$(date '+%H:%M:%S') Cluster $CLUSTER_NAME Status is $COND"
done
echo "EKS cluster created."

# Get cluster endpoint and certificate for configuring kubectl to connect to the
# cluster
ENDPOINT=$(aws eks describe-cluster --name $CLUSTER_NAME \
               --query cluster.endpoint --output text)
CERTIFICATE_AUTH=$(aws eks describe-cluster --name $CLUSTER_NAME \
                       --query cluster.certificateAuthority.data --output text)

### 3. Setup kubectl config for connecting to cluster
mkdir -p ~/.kube
cp ./kubeconfig.template ~/.kube/config-$CLUSTER_NAME
sed "s|<endpoint-url>|$ENDPOINT|g" -i ~/.kube/config-$CLUSTER_NAME
sed "s|<base64-encoded-ca-cert>|$CERTIFICATE_AUTH|g" -i ~/.kube/config-$CLUSTER_NAME
sed "s|<cluster-name>|$CLUSTER_NAME|g" -i ~/.kube/config-$CLUSTER_NAME

echo "export KUBECONFIG=~/.kube/config-$CLUSTER_NAME:\$KUBECONFIG" >> ~/.bashrc
export KUBECONFIG=~/.kube/config-$CLUSTER_NAME:$KUBECONFIG

### 4. Create worker nodes
aws cloudformation create-stack --stack-name $CLUSTER_NAME-workers \
    --template-body file://scanner-eks-nodegroup.yaml \
    --capabilities CAPABILITY_IAM \
    --parameters \
	ParameterKey=ClusterName,ParameterValue=$CLUSTER_NAME \
    ParameterKey=ClusterControlPlaneSecurityGroup,ParameterValue=$SECURITY_GROUP_IDS \
    ParameterKey=NodeGroupName,ParameterValue=$CLUSTER_NAME-workers-node-group \
	ParameterKey=NodeAutoScalingGroupMinSize,ParameterValue=$NODESDESIRED \
    ParameterKey=NodeAutoScalingGroupMaxSize,ParameterValue=$MAXNODES \
    ParameterKey=NodeInstanceType,ParameterValue=$INSTANCE_TYPE \
    ParameterKey=NodeImageId,ParameterValue=$AMI \
    ParameterKey=KeyName,ParameterValue=$KEYNAME \
    ParameterKey=VpcId,ParameterValue=$VPC_ID \
    ParameterKey=Subnets,ParameterValue=\"$SUBNET_IDS\"

echo "Waiting for EKS worker node group to be created... (may take a while)"
aws cloudformation wait stack-create-complete --stack-name $CLUSTER_NAME-workers
echo "EKS worker node group created."

# CHECK FOR SUCCESSFUL STACK CREATION
STACK_STATUS=$(aws cloudformation describe-stacks|jq -r ".Stacks[] | select(.StackName == \"$CLUSTER_NAME-workers\") | .StackStatus")
echo "STACK_STATUS=$STACK_STATUS"
if ! [ "$STACK_STATUS" = "CREATE_COMPLETE" ]
then
	errorexit "Stack Creation Failure: $STACK_STATUS"
fi

aws cloudformation describe-stacks --stack-name $CLUSTER_NAME-workers

NODE_INSTANCE_ROLE=$(aws cloudformation describe-stacks --stack-name $CLUSTER_NAME-workers \
             | jq -r '.Stacks[0].Outputs[] | select(.OutputKey=="NodeInstanceRole") | .OutputValue')

rm -f aws-auth-cm.yaml
curl -O https://amazon-eks.s3-us-west-2.amazonaws.com/1.10.3/2018-06-05/aws-auth-cm.yaml
sed "s*<ARN of instance role (not instance profile)>*$NODE_INSTANCE_ROLE*g" -i aws-auth-cm.yaml
kubectl apply -f aws-auth-cm.yaml

### 5. Install cloudwatch adapter to support logging to cloud watch
# HELM is broken glibc versioning problem
#helm install --name kube2iam stable/kube2iam
#helm install --name cloudwatch \
#  --set awsRegion=us-east-1 \
#  --set awsRole=cloudwatch \
#    incubator/fluentd-cloudwatch

# Add role binding to allow kube2iam to work correctly
# See https://github.com/heptio/aws-quickstart/issues/75
kubectl create clusterrolebinding kube-system-default-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=default:default

### 6. Tell master and worker pods about db path
sed "s|<BUCKET>|$BUCKET|g;s|<REGION>|$REGION|g" scanner-config.yaml.template > scanner-config.yml
kubectl apply -f scanner-config.yml
sed "s|<BUCKET>|$BUCKET|g;s|<REGION>|$REGION|g" config.toml.template > config.toml

### 7. Add dashboard (By Blakley)
#kubectl create -f https://raw.githubusercontent.com/kubernetes/dashboard/master/aio/deploy/recommended/kubernetes-dashboard.yaml
#nohup kubectl proxy&
#	http://localhost:8001/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy/
## OR: export DASHURL=`kubectl cluster-info|grep "Kubernetes master"|sed '/^.*at /s///;s/$/\/ui/'`
##TOKEN=$(kubectl -n kube-system get secret kubernetes-dashboard-token-45nhk -o json|jq -r '.data.token')
#kubectl apply -f dashboard-adminuser.yaml

