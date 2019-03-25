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
### 2. Deploy master and worker services

# Create secret for sharing AWS credentials with instances
kubectl delete secret aws-storage-key 2>/dev/null >/dev/null # raises unnecessary error if key doesn't exist
kubectl create secret generic aws-storage-key \
        --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
        --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

# Replace REPO_NAME with the location of the docker image
sed "s|<REPO_NAME>|$REPO_URI:scanner-master|g;s|<AWSACCT>|$AWSACCT|g" master.yml.template > master.yml
sed "s|<REPO_NAME>|$REPO_URI:scanner-worker|g;s|<AWSACCT>|$AWSACCT|g" worker.yml.template > worker.yml

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

