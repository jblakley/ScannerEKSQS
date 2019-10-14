
import scannerpy as scan
import scannertools.face_detection
import scannertools.vis
import scannertools.imgproc

import os.path
import subprocess as sp

example_video_path = 'star_wars_heros.mp4'

# example_video_path = "Modern_Family_3min.m4v"

if not os.path.isfile(example_video_path):
    print("File does not exist: %s" % example_video_path)
    outp = sp.check_output(
        '''
        wget https://storage.googleapis.com/scanner-data/tutorial_assets/star_wars_heros.mp4
        ''',
        shell=True).strip().decode('utf-8')
else:
    print("Using: %s" % example_video_path)

print('Connecting to Scanner database/client...')
db = scan.Client()

print('Running Scanner job...')
# example_video_path = 'star_wars_heros.mp4'
print(db.summarize())
# db.load_op('/usr/local/libscanner_stdlib.so',
#            '/usr/local/stdlib_pb2.py')
db.load_op('/opt/scanner/build/stdlib/libscanner_stdlib.so',
           '/opt/scanner/build/stdlib/stdlib_pb2.py')


db.load_op("/opt/scanner/examples/tutorials/resize_op/libresize_op.so",
        "/opt/scanner/examples/tutorials/resize_op/resize_pb2.py")


input_stream = scan.NamedVideoStream(db, 'example', path=example_video_path)
frames = db.io.Input([input_stream])
size_frame = db.ops.MyResize(frame=frames, width=640, height=480)
face_frame = db.ops.OpenVino_Face_Obfuscate(frame=size_frame, conf_threshold=0.5)
r_frame = db.ops.Plate_Obfuscate(frame=face_frame, conf_threshold=0.1)

# face_frames = db.ops.MTCNNDetectFaces(frame=r_frame)
# boxed_face_frames = db.ops.DrawBboxes(frame=face_frames, bboxes=face_frames)


output_stream = scan.NamedVideoStream(db, 'example-obfuscated')
output = db.io.Output(r_frame, [output_stream])
# output = db.io.Output(boxed_face_frames, [output_stream])
db.run(output, scan.PerfParams.estimate(), cache_mode=scan.CacheMode.Overwrite)

output_stream.save_mp4('resized-video')

print(db.summarize())

print('Complete!')