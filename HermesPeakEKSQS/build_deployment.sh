#!/bin/bash
### 0. Things to do up front (Blakley)
set -ex

#	echo KUBECONFIG=$KUBECONFIG
#	kubectl apply -f spark-config.yml # In case of changes -- already done on cluster create

test -z "$AWS_ACCESS_KEY_ID" && \
	export AWS_ACCESS_KEY_ID=$(grep aws_access_key_id ~/.aws/credentials|awk '{print $3}')
	
test -z "$AWS_ACCESS_KEY_ID" && \
	(echo "Could not find AWS_ACCESS_KEY_ID";exit 1)

test -z "$AWS_SECRET_ACCESS_KEY" && \
	export AWS_SECRET_ACCESS_KEY=$(grep aws_secret_access_key ~/.aws/credentials|awk '{print $3}')

test -z "$AWS_SECRET_ACCESS_KEY" && \
	(echo "Could not find AWS_SECRET_ACCESS_KEY";exit 1)

test -z "$SPARK_HOME" && SPARK_HOME=/root/spark
test -z "$REGION" && REGION=us-east-1

# Update the container version tag
test -f ./cversion || echo 0 > ./cversion
CVER=$(expr $(cat ./cversion) + 1 )
echo $CVER > ./cversion
CVER=V$CVER

### 1. Check if container repo exists
aws ecr describe-repositories --repository-names spark
REG_EXISTS=$?
if [ $REG_EXISTS -ne 0 ]; then
    # Create container repo
    aws ecr create-repository --repository-name spark
fi

# Get container repo URI
REPO_URI=$(aws ecr describe-repositories --repository-names spark | jq -r '.repositories[0].repositoryUri')
echo $REPO_URI
CONTAINERTAG=$REPO_URI:$CVER

### 2. Build docker images
cp -prvf QSexamples $SPARK_HOME  # Put the examples and jobs into the spark directory
LWD=$(pwd)
cd $SPARK_HOME
docker build --no-cache -t $CONTAINERTAG -f $LWD/Dockerfile.spark . # Take out no-cache?? TODO

#aws configure set default.region ${REGION}

# Provides an auth token to enable pushing to container repo
LOGIN_CMD=$(aws ecr get-login --no-include-email)
eval $LOGIN_CMD

# Push master and worker images
docker push $CONTAINERTAG

