#!/bin/bash
# Run with "dot space script" syntax: ". ./setkubectl.sh"
WHOIAM=$(whoami)
HOMEDIR=$(ls -d ~)
DEFAULTUSER=/home/ubuntu
CLUSTER_NAME=$1
echo "searching for configuration file in /$WHOIAM $HOMEDIR $DEFAULTUSER"

if ! [ "$CLUSTER_NAME" == "" ]
then
	echo "CLUSTER_NAME=$CLUSTER_NAME"
	KUBECFILE="/$WHOIAM/.kube/config-$CLUSTER_NAME"
	test -f "$KUBECFILE" || KUBECFILE="$HOMEDIR/.kube/config-$CLUSTER_NAME"
	test -f "$KUBECFILE" || KUBECFILE="$DEFAULTUSER/.kube/config-$CLUSTER_NAME"
	test -f "$KUBECFILE" && export KUBECONFIG=$KUBECFILE
	echo KUBECONFIG=$KUBECONFIG
else
	echo "CLUSTER_NAME not set"
	exit 1
fi

