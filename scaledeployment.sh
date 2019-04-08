#!/bin/bash
NUMINSVC=$(aws autoscaling describe-auto-scaling-groups |jq -r '.AutoScalingGroups[].Instances[].LifecycleState'|wc|awk '{print $1}')
REPLICAS=$(expr $NUMINSVC - 1)
SLEEP=10

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
