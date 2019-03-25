#!/bin/bash
### 0. Things to do up front (Blakley)

echo KUBECONFIG=$KUBECONFIG
kubectl apply -f scanner-config.yml # In case of changes -- already done on cluster create

test -z "$AWS_ACCESS_KEY_ID" && \
	export AWS_ACCESS_KEY_ID=$(grep aws_access_key_id ~/.aws/credentials|awk '{print $3}')
	
test -z "$AWS_ACCESS_KEY_ID" && \
	(echo "Could not find AWS_ACCESS_KEY_ID";exit 1)

test -z "$AWS_SECRET_ACCESS_KEY" && \
	export AWS_SECRET_ACCESS_KEY=$(grep aws_secret_access_key ~/.aws/credentials|awk '{print $3}')

test -z "$AWS_SECRET_ACCESS_KEY" && \
	(echo "Could not find AWS_SECRET_ACCESS_KEY";exit 1)
	
test -z "$REGION" && \
	REGION=us-east-1

test -z "$CONTAINER_TAG" && \
	export CONTAINER_TAG=jpablomch/scanner-aws:latest

# Create the number of replicas == number of k8s nodes minus 1 for the master
test -z "$NODESDESIRED" && \
	NODESDESIRED=$(kubectl get nodes -o json| jq -r '.items[].status.addresses[] | select(.type=="InternalIP") | .address'|wc|awk '{print $1}')
REPLICAS=$(expr $NODESDESIRED - 1)
echo "Creating $REPLICAS of worker node"

### 1. Check if container repo exists
aws ecr describe-repositories --repository-names scanner
REG_EXISTS=$?
if [ $REG_EXISTS -ne 0 ]; then
    # Create container repo
    aws ecr create-repository --repository-name scanner
fi
#	echo $AWS_ACCESS_KEY_ID
#	echo $AWS_SECRET_ACCESS_KEY
# Get container repo URI
REPO_URI=$(aws ecr describe-repositories --repository-names scanner | jq -r '.repositories[0].repositoryUri')
echo $REPO_URI

### 2. Build master and worker docker images
docker pull $CONTAINER_TAG

docker build -t $REPO_URI:scanner-master . \
       -f Dockerfile.master

docker build -t $REPO_URI:scanner-worker . \
       -f Dockerfile.worker

aws configure set default.region ${REGION}

# Provides an auth token to enable pushing to container repo
LOGIN_CMD=$(aws ecr get-login --no-include-email)
eval $LOGIN_CMD

# Push master and worker images
docker push $REPO_URI:scanner-master
docker push $REPO_URI:scanner-worker
