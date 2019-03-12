#!/bin/bash
# This script will change the number of nodes in the cluster and then adjust the number of worker pods
NEWMAX=$1
if [ $NEWMAX -lt 2 ]
then
	echo "Number of nodes must be at least 2 -- one for master and one for worker: $NEWMAX"
	exit 1
fi
SLEEP=10
ASGNAME=$(aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].AutoScalingGroupName')
echo Changing auto scaling group $ASGNAME to desired capacity $NEWMAX
aws autoscaling set-desired-capacity --auto-scaling-group-name $ASGNAME --desired-capacity $NEWMAX

NUMINSVC=$(aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].Instances[].LifecycleState'|wc|awk '{print $1}')
while [ $NEWMAX -ne $NUMINSVC ]
do
	echo "Waiting for number of nodes to stabilize: $NUMINSVC going to $NEWMAX"
	sleep $SLEEP
	kubectl get nodes
	NUMINSVC=$(aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].Instances[].LifecycleState'|wc|awk '{print $1}')
done

# NUMNODES=$(kubectl get nodes -o json| jq -r '.items[].status.addresses[] | select(.type=="InternalIP") | .address'|wc|awk '{print $1}')

REPLICAS=$(expr $NUMINSVC - 1)
echo Changing k8s worker replicas to $REPLICAS "(Leave a node for the master)"
kubectl scale deployment/scanner-worker --replicas=$REPLICAS

PODINSVC=$(kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}')

while [ $REPLICAS -ne $PODINSVC ]
do
	echo "Waiting for number of worker pods to stabilize: $PODINSVC going to $REPLICAS"
	sleep $SLEEP
	kubectl get pods
#	PODINSVC=$(kubectl get pods -o json|jq -r '.items[].status.containerStatuses[] | select(.name=="scanner-worker") | select(.ready==true) ' \
#     |jq -r '.name'|wc|awk '{print $1}')
	PODINSVC=$(kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}')
done

# Report results
kubectl get nodes ; kubectl get pods
