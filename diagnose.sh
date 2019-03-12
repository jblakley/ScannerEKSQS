#!/bin/bash
kubectl get pods
kubectl get pod --selector=app=scanner-master -o json
kubectl logs --selector=app=scanner-worker
kubectl logs --selector=app=scanner-master
kubectl describe pods --selector=app=scanner-master
kubectl describe pods --selector=app=scanner-worker
kubectl get services scanner-master