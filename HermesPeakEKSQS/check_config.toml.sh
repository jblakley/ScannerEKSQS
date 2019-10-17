#!/bin/bash

CLNT="/root/.scanner"
echo $CLNT
cat $CLNT/config.toml

EFS=/efs-sdb
echo -e "\n$EFS"
cat $EFS/config.toml


MSTR=$(kubectl get pods -o json|jq -r '.items[].metadata.name'|grep master)
echo -e "\n$MSTR"
kubectl exec -it $MSTR cat /root/.scanner/config.toml

WRKRS=$(kubectl get pods -o json|jq -r '.items[].metadata.name'|grep worker)
for xx in $WRKRS
do
	echo -e "\n$xx"
	kubectl exec -it $xx cat /root/.scanner/config.toml
done