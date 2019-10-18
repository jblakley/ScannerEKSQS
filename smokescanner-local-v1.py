#!/usr/bin/env python3
import scannerpy as scan
import scannertools.face_detection
import scannertools.vis
# import scannertools.imgproc

import os.path
import subprocess as sp
import shutil
import time, datetime



def main():
    
    os.environ['PATH'] = os.environ['PATH'] + ":."

    example_video_path = 'star_wars_heros.mp4'
    
    ''' Get the media locally '''
    if not os.path.isfile(example_video_path):
        print("File does not exist: %s" % example_video_path)
        retcode = oscmd("wget https://storage.googleapis.com/scanner-data/tutorial_assets/star_wars_heros.mp4")    
    partlist = [example_video_path]    
    print('Connecting to Scanner database/client...')
    db = scan.Client()
    print(db.summarize())
    db.load_op("/opt/scanner/examples/tutorials/resize_op/libresize_op.so",
            "/opt/scanner/examples/tutorials/resize_op/resize_pb2.py")
    instreamlist = []
    outstreamlist = []
    for fname in partlist:
        if not os.path.isfile(fname):
            print("Input file %s does not exist, skipping" % fname)
            continue
     
        bname = os.path.basename(fname)[:-4] # drop the suffix
        instreamlist.append(scan.NamedVideoStream(db, bname ,path=fname))
        outfname = 'processed-%s-%s' % (humandate(time.time()),bname)
        outstreamlist.append(scan.NamedVideoStream(db,outfname))

    input_frames = db.io.Input(instreamlist)
    
    ''' Pipeline '''
    resized_frames = db.ops.MyResize(frame=input_frames, width=640, height=480)
    sampled_frames = db.streams.Stride(resized_frames, [3])
    face_frames = db.ops.MTCNNDetectFaces(frame=sampled_frames)
    boxed_face_frames = db.ops.DrawBboxes(frame=sampled_frames, bboxes=face_frames)
     
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
    