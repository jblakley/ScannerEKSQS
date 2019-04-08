#!/bin/bash
# This script will change the number of nodes in the cluster and then adjust the number of worker pods
# The deployment must be running for this to work
NEWMAX=$1
PODDESIRED=$(expr $NEWMAX - 1)
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
# Scaling the cluster down
if [ $NEWMAX -lt $NUMINSVC ]
then
	# Scale the pods down first
	PODINSVC=$(kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}')
	if [ $PODINSVC -gt $PODDESIRED ]
	then
		echo "Reducing the number of worker pods from $PODINSVC to $PODDESIRED"
		kubectl scale deployment/scanner-worker --replicas=$PODDESIRED
		while [ $PODINSVC -ne $PODDESIRED ]
		do
			PODINSVC=$(kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}')
			kubectl get pods
			sleep $SLEEP
		done
	fi
fi
# Now scale the nodes
while [ $NEWMAX -ne $NUMINSVC ]
do
	echo "Waiting for number of nodes to stabilize: $NUMINSVC going to $NEWMAX"
	sleep $SLEEP
	kubectl get nodes
	NUMINSVC=$(kubectl get nodes|grep Ready|grep -v NotRead|wc|awk '{print $1}')
done

# Now scale pods -- redundant if scaling down. Already set above
kubectl scale deployment/scanner-worker --replicas=$PODDESIRED
echo "Setting the number of worker pods to $PODDESIRED"
PODINSVC=$(kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}')
if [ $PODINSVC -eq 0 ]
then
	echo "No pods in service -- deployment must not be running. Done ..."
	exit 0
fi
while [ $PODINSVC -ne $PODDESIRED ]
do
    sleep $SLEEP
    kubectl get pods
	PODINSVC=$(kubectl get pods|egrep -e "worker.*Running"|wc|awk '{print $1}')
done

