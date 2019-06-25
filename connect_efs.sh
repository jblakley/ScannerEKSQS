
### 7. Connect efs
test -d /efs || mkdir /efs
test -z "$REGION" && REGION=us-east-1
EFSVOL=$(aws efs describe-file-systems|jq -r '.FileSystems[].FileSystemId')
mountpoint -q /efs || mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFSVOL.efs.$REGION.amazonaws.com:/ /efs

if test -z "$(kubectl get pv -o json|jq -r '.items[].metadata.name')"
then
	kubectl apply -f efs-manifest.yaml
	kubectl get pods
#	EFSRUNNING=$(kubectl get pods|egrep '^efs.*Running')
	WAITTIME=0
	while test -z "$(kubectl get pv -o json|jq -r '.items[].metadata.name')"
	do
		sleep 3
		kubectl get pods
		WAITTIME=$(expr $WAITIME + 3)
	done
	
	PVNAME=$(kubectl get pv -o json|jq -r '.items[].metadata.name')
	kubectl patch pv $PVNAME -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
fi
for xx in pv pvc configmap storageclass
do
	echo "kubectl get $xx"
	kubectl get $xx
done

