test -z "$REGION" && REGION=us-east-1
test -z "$EFSVOL" && EFSVOL=$(aws efs describe-file-systems|jq -r '.FileSystems[].FileSystemId')

PVCNAME=$(kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == "efs") | .spec.volumeName')
mountpoint -q /efs || mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFSVOL.efs.$REGION.amazonaws.com:/ /efs
mountpoint -q /efsc || mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFSVOL.efs.$REGION.amazonaws.com:/efs-${PVCNAME} /efsc
PVCNAME=$(kubectl get pvc -o json|jq -r '.items[] | select(.metadata.name == "efs-sdb") | .spec.volumeName')
mountpoint -q /efs-sdb || mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFSVOL.efs.$REGION.amazonaws.com:/efs-sdb-${PVCNAME} /efs-sdb
mountpoint -q /root/.scanner || mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFSVOL.efs.$REGION.amazonaws.com:/efs-sdb-${PVCNAME} /root/.scanner
