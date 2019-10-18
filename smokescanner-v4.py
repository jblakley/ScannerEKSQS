#!/usr/bin/env python3
import scannerpy as scan
import scannertools.face_detection
import scannertools.vis
import scannertools.imgproc

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np

import os.path
import subprocess as sp
import shutil
import time, datetime

@scan.register_python_op()
def CloneChannels(config, frame: scan.FrameType) -> scan.FrameType:
    return np.dstack([frame for _ in range(config.args['replications'])])


def main():
    
    os.environ['KUBECONFIG'] = cmd0("ls -tr /root/.kube/config-*|tail -1")
    os.environ['PATH'] = os.environ['PATH'] + ":."
    os.environ['AWS_ACCESS_KEY_ID'] = cmd0('grep aws_access_key_id /root/.aws/credentials|cut -f2 -d "="')
    os.environ['AWS_SECRET_ACCESS_KEY'] = cmd0('grep aws_secret_access_key /root/.aws/credentials|cut -f2 -d "="')


#     S3M="SecondaryOut"
    EFSM='/efsc/Media/TVandMovies'
    EFSR="/efsc/Results"
    example_video_path = '/efsc/Media/star_wars_heros.mp4'
#     example_video_path = 'star_wars_heros.mp4'
    partlist = [example_video_path]    
    
    print('Finding master IP...')
    ip = cmd0("kubectl get services scanner-master --output json | jq -r '.status.loadBalancer.ingress[0].hostname'")
    port = cmd0("kubectl get svc/scanner-master -o json | jq '.spec.ports[0].port' -r")
    master = '{}:{}'.format(ip, port)
    print('Master ip: {:s}'.format(master))

    with open('config.toml', 'w') as f:
        config_text = cmds("kubectl get configmaps scanner-configmap -o json | jq '.data[\"config.toml\"]' -r")
        f.write(config_text)

    print('Connecting to Scanner database/client...')
    db = scan.Client(
        master=master,
        start_cluster=False,
        config_path='./config.toml',
        grpc_timeout=60)

#     db = scan.Client() # Local

    print(db.summarize())

    db.load_op("/opt/scanner/examples/tutorials/resize_op/libresize_op.so",
            "/opt/scanner/examples/tutorials/resize_op/resize_pb2.py")
     
    flist = os.listdir(EFSM) 
#     flist = cmd("aws s3 ls s3://s3-scanner-utilities-1/SecondaryOut/|awk '{print $4}'") # TODO parameterize
    flist = [xx for xx in flist if xx.endswith(('.mp4','.m4v'))] # Filter the files that work -- i.e., no yuv or mpg, etc
    fulllist = ["%s/%s" % (EFSM,xx) for xx in flist]
#     partlist = fulllist[3:4] # Comment out to use example_video

    instreamlist = []
    outstreamlist = []
    for fname in partlist:
        if not os.path.isfile(fname):
            print("Input file %s does not exist, skipping" % fname)
            continue
        
        bname = os.path.basename(fname)[:-4] # drop the suffix
#         sname = bname.replace("_","")
        instreamlist.append(scan.NamedVideoStream(db, bname ,path=fname))
        outfname = 'processed-%s-%s' % (humandate(time.time()),bname)
        outstreamlist.append(scan.NamedVideoStream(db,outfname))

    input_frames = db.io.Input(instreamlist)
    
    ''' Pipeline '''
    resized_frames = db.ops.MyResize(frame=input_frames, width=640, height=480)
    sampled_frames = db.streams.Stride(resized_frames, [3])
    face_frames = db.ops.MTCNNDetectFaces(frame=sampled_frames)
    boxed_face_frames = db.ops.DrawBboxes(frame=sampled_frames, bboxes=face_frames)
#     genders = db.ops.DetectGender(frame=sampled_frames,bboxes=face_frames)
    gray_frames = db.ops.ConvertColor(frame=boxed_face_frames, conversion=['COLOR_RGB2GRAY'])
    gray_frames3 = db.ops.CloneChannels(frame=gray_frames, replications=3)
     
    run_frames = boxed_face_frames
    
    output = db.io.Output(run_frames, outstreamlist)
    
    db.run(output, scan.PerfParams.estimate(), cache_mode=scan.CacheMode.Ignore)
    
    for output_stream in outstreamlist:
        if os.path.isdir(EFSR):
            sname = os.path.join(EFSR,output_stream.name())
            print("Saving %s" % sname)
            output_stream.save_mp4(sname)

    print(db.summarize())
    
    print('Complete!')
    
    
def oscmd(cmdstr): # Prints out to console and returns exit status
    return os.system(cmdstr)

def cmd(cmdstr): # Returns the output of the command as a list
    output = os.popen(cmdstr).read().split("\n")
    return output

def cmd0(cmdstr): # Returns first line of output as a string
    retlst = cmd(cmdstr)
    return retlst[0].strip()

def cmds(cmdstr): # Returns all output  of the command as a string
    output = os.popen(cmdstr).read()
    return output

def cmd_subp(cmdstr):
    args = shlex.split(cmdstr)
    procdata = subprocess.Popen(args)
    return procdata

def humandate(unixtime):
    retstr = datetime.datetime.fromtimestamp(unixtime).strftime('%Y-%m-%d-%H-%M-%S-%f')
    return retstr

if __name__ == '__main__': main()
    