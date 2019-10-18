
### 7. Connect efs
test -d /efs || mkdir /efs
test -z "$REGION" && REGION=us-east-1
EFSVOL=$(aws efs describe-file-systems|jq -r '.FileSystems[].FileSystemId')
mountpoint -q /efs || mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFSVOL.efs.$REGION.amazonaws.com:/ /efs

if test -z "$(kubectl get pods|egrep '^efs.*Running')"
then
	kubectl apply -f efs-manifest.yaml
	kubectl get pods
#	EFSRUNNING=$(kubectl get pods|egrep '^efs.*Running')
	WAITTIME=0
	while test -z "$(kubectl get pods|egrep '^efs.*Running')" # Wait until efs-provisioner is running
	do
		sleep 3
		kubectl get pods
		WAITTIME=$(expr $WAITIME + 3)
	done
	while test -z "$(kubectl get pv -o json|jq -r '.items[].metadata.name')" # Wait until PVC is created
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

. ./remount_efs.sh
if mountpoint -q /efsc
then
	test -d /efsc/Media || cp -p -v -r /efs/Media /efsc/
	test -d /efsc/Results || mkdir /efsc/Results
fi
mountpoint -q /efs-sdb && cp config.toml /efs-sdb/