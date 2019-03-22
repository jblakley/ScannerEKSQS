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
docker pull jpablomch/scanner-aws:latest

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

### 2. Deploy master and worker services

# Create secret for sharing AWS credentials with instances
kubectl delete secret aws-storage-key 2>/dev/null >/dev/null # raises unnecessary error if key doesn't exist
kubectl create secret generic aws-storage-key \
        --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
        --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

# Replace REPO_NAME with the location of the docker image
sed "s|<REPO_NAME>|$REPO_URI:scanner-master|g" master.yml.template > master.yml
sed "s|<REPO_NAME>|$REPO_URI:scanner-worker|g" worker.yml.template > worker.yml

# Record existing replicas for worker so we can scale the service after deleting
#REPLICAS=$(kubectl get deployments scanner-worker -o json | jq '.spec.replicas' -r)



# Delete and then redeploy the master and worker services
kubectl delete deploy --all

# Delete deploy does not get rid of the old load balancer -- they build up over time, so delete it
LBDNS=$(kubectl get services scanner-master --output json | jq -r '.status.loadBalancer.ingress[0].hostname')
LBS=$(aws elb describe-load-balancers|jq -r '.LoadBalancerDescriptions[]')
LBTHIS=$(echo $LBS|jq -r "select(.DNSName==\"$LBDNS\")"|jq -r '.LoadBalancerName')
test -n "$LBTHIS" && aws elb delete-load-balancer --load-balancer-name $LBTHIS

kubectl delete service scanner-master 2>/dev/null >/dev/null # raises unnecessary error if service doesn't exist
kubectl create -f master.yml
kubectl create -f worker.yml

# If there was an existing service, scale the new one back up to the same size
if [[ "$REPLICAS" ]]; then
    kubectl scale deployment/scanner-worker --replicas=$REPLICAS
fi

### 3. Expose the master port for the workers to connect to
kubectl expose -f master.yml --type=LoadBalancer --target-port=8080 --selector='app=scanner-master'

