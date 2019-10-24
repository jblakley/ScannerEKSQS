#!/usr/bin/env python3


import sys

import vdms
import json
from HPEKSutils import *


def main():
    
    
    os.environ['KUBECONFIG'] = cmd0("ls -tr /root/.kube/config-*|tail -1")
    os.environ['PATH'] = os.environ['PATH'] + ":."
    os.environ['AWS_ACCESS_KEY_ID'] = cmd0('grep aws_access_key_id /root/.aws/credentials|cut -f2 -d "="')
    os.environ['AWS_SECRET_ACCESS_KEY'] = cmd0('grep aws_secret_access_key /root/.aws/credentials|cut -f2 -d "="')

    db = vdms.vdms()

    ip = cmd0("kubectl get services vdms --output json | jq -r '.status.loadBalancer.ingress[0].hostname'")
#     ip = "localhost"
    db.connect(ip)
    
    props = {}
    props["place"] = "Mt Rainier"
    props["id"] = 4543
    props["type"] = "Volcano"
    
    addEntity = {}
    addEntity["properties"] = props
    addEntity["class"] = "Hike"
    
    
    query = {}
    query["AddEntity"] = addEntity
    
    all_queries = []
    all_queries.append(query)
    
    print ("Query Sent: ")
    print(json.dumps(all_queries, indent = 4))
    
    response, res_arr = db.query(all_queries)  
    print ("VDMS Response: ")
    print(json.dumps(response, indent=4))

    # As an example, we build the FindEntity command directly
    query = {
              "FindEntity" : {
                 "class": "Hike",
                 "_ref": 3,
                 "constraints": {
                     "id": ["==", 4543]
                 }
              }
           }
    
    all_queries = []
    all_queries.append(query)
    
    props = {}
    props["name"]     = "Tom"
    props["lastname"] = "Lluhs"
    props["id"]       = 453
    
    link = {}
    link["ref"] = 3
    
    addEntity = {}
    addEntity["properties"] = props
    addEntity["class"] = "Person"
    addEntity["link"] = link
    
    query = {}
    query["AddEntity"] = addEntity
    
    all_queries.append(query)
    
    props = {}
    props["name"]     = "Sophia"
    props["lastname"] = "Ferdinand"
    props["id"]       = 454
    
    link = {}
    link["ref"] = 3
    
    addEntity = {}
    addEntity["properties"] = props
    addEntity["class"] = "Person"
    addEntity["link"] = link
    
    query = {}
    query["AddEntity"] = addEntity
    
    all_queries.append(query)
    
    print ("Query Sent:")
    aux_print_json(all_queries)
    
    response, res_arr = db.query(all_queries)
    
    print ("VDMS Response: ")
    aux_print_json(response)      
    print("Finished")
    sys.exit(0)    

def aux_print_json(inlist):
    print(json.dumps(inlist, indent=4))
if __name__ == '__main__': main()