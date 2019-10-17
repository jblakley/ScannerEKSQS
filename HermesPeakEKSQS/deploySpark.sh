#!/bin/bash
### 0. Things to do up front (Blakley)
# Also done in create but allows reseting of bucket during deployment TODO -- remove from create
#	sed "s|<BUCKET>|$BUCKET|g;s|<REGION>|$REGION|g" spark-config.yaml.template > spark-config.yml
#	kubectl apply -f spark-config.yml
#	sed "s|<BUCKET>|$BUCKET|g;s|<REGION>|$REGION|g" config.toml.template > config.toml
#	
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
	
test -z "$REGION" && \
	REGION=us-east-1

test -z "$CLUSTERNAME" && \
	CLUSTERNAME=JRBSPARKQS2
	
test -z "$NODEGROUP_LABEL" && \
	NODEGROUP_LABEL=alpha.eksctl.io/nodegroup-name

# Create secret for sharing AWS credentials with instances
#kubectl delete secret aws-storage-key 2>/dev/null >/dev/null # raises unnecessary error if key doesn't exist
#kubectl create secret generic aws-storage-key \
#        --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
#        --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

# Get info needed for spark-submit

CVER=V$(cat ./cversion)
# Get container repo URI
REPO_URI=$(aws ecr describe-repositories --repository-names spark | jq -r '.repositories[0].repositoryUri')
echo $REPO_URI
CONTAINERTAG=$REPO_URI:$CVER

ENDPOINT=$(aws eks describe-cluster --name $CLUSTERNAME | jq -r '.cluster.endpoint')
echo $ENDPOINT

REPLICAS=$(kubectl get nodes -o json|jq -r '.items[].metadata.labels | select(."alpha.eksctl.io/nodegroup-name" == "Spark") | ."alpha.eksctl.io/nodegroup-name"'|wc|awk '{print $1}')
REPLICAS=$(expr $REPLICAS - 1)
# Run deployment and execution tests

# JAVA SMOKE TEST
#	
#echo "Running JAVA SMOKE TEST"
#spark-submit \
#    --master k8s://${ENDPOINT} \
#    --deploy-mode cluster \
#    --name spark-pi \
#    --class org.apache.spark.examples.SparkPi \
#    --conf spark.executor.instances=2 \
#    --conf spark.kubernetes.container.image=$CONTAINERTAG \
#    local:///opt/spark/examples/jars/spark-examples_2.11-2.4.3.jar
    
# PYTHON SMOKE TEST

# Add PYSPARK_MAJOR_PYTHON_VERSION=3 to $SPARK_HOME/kubernetes/dockerfiles/spark/entrypoint.sh

echo "Running PYTHON SMOKE TEST"

PVCNAME=$(kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == "efs") | .spec.volumeName')
	
spark-submit \
    --master k8s://${ENDPOINT} \
    --deploy-mode cluster \
    --name spark-pi \
    --conf spark.executor.instances=$REPLICAS \
    --conf spark.kubernetes.container.image=$CONTAINERTAG \
    --conf spark.kubernetes.node.selector.$NODEGROUP_LABEL=Spark \
    --conf spark.kubernetes.driver.volumes.persistentVolumeClaim.$PVC.mount.path=/efs \
    --conf spark.kubernetes.driver.volumes.persistentVolumeClaim.$PVC.options.claimName=efs \
    --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.$PVC.mount.path=/efs \
    --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.$PVC.options.claimName=efs \
	local:///opt/spark/QSexamples/smokepi.py

# To keep driver pod running after result, don't do spark.stop() at the end
# get to the UI of a running driver:
# 	kubectl port-forward <driver POD ID> 4040:4040
# go to localhost:4040



