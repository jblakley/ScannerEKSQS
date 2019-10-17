#!/bin/bash
# Wait for cluster to be created...
export CLUSTER_NAME=$1
echo "Waiting for EKS cluster to be created... (may take a while)"
COND=$(aws eks describe-cluster --name $CLUSTER_NAME --query cluster.status)
while ! [ "$COND" = "\"ACTIVE\"" ]; do
  sleep 5
  COND=$(aws eks describe-cluster --name $CLUSTER_NAME --query cluster.status)
  echo Cluster Status is "$COND"
done