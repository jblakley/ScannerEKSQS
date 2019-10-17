
#!/bin/bash
env|sort
spark-submit \
            --master k8s://$1 \
            --deploy-mode cluster \
            --name spark-pi \
            --conf spark.executor.instances=2 \
            --conf spark.kubernetes.container.image=$2 \
            local:///opt/spark/QSexamples/pi.py