from scannerpy import Database, DeviceType, Job
from scannerpy.stdlib import pipelines
import subprocess
import cv2
import sys
import os.path
import subprocess as sp
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../..')
# import util

movie_path = 'star_wars_heros.mp4'

if not os.path.isfile(movie_path):
    print("File does not exist: %s" % movie_path)
    outp = sp.check_output(
        '''
        wget https://storage.googleapis.com/scanner-data/tutorial_assets/star_wars_heros.mp4
        ''',
        shell=True).strip().decode('utf-8')

else:
    print("Using: %s" % movie_path)
    
print('Finding master IP...')
ip = sp.check_output(
    '''
    kubectl get services scanner-master --output json | jq -r '.status.loadBalancer.ingress[0].hostname'
    ''',
    shell=True).strip().decode('utf-8')

port = sp.check_output(
    '''
kubectl get svc/scanner-master -o json | \
jq '.spec.ports[0].port' -r
''',
    shell=True).strip().decode('utf-8')

master = '{}:{}'.format(ip, port)
print('Master ip: {:s}'.format(master))

with open('config.toml', 'w') as f:
    config_text = sp.check_output(
        '''
        kubectl get configmaps scanner-configmap -o json | \
        jq '.data["config.toml"]' -r
        ''',
        shell=True).strip().decode('utf-8')
    f.write(config_text)

    
print('Detecting faces in movie {}'.format(movie_path))
movie_name = os.path.splitext(os.path.basename(movie_path))[0]

db = Database(
    master=master,
    start_cluster=False,
    config_path='./config.toml',
    grpc_timeout=60)

print('Ingesting video into Scanner ...')
[input_table], _ = db.ingest_videos(
    [(movie_name, movie_path)], force=True)

sampler = db.streams.All
sampler_args = {}

print('Detecting faces...')
[bboxes_table] = pipelines.detect_faces(
    db, [input_table.column('frame')],
    sampler,
    sampler_args,
    movie_name + '_bboxes')

print('Drawing faces onto video...')
frame = db.sources.FrameColumn()
sampled_frame = sampler(frame)
bboxes = db.sources.Column()
out_frame = db.ops.DrawBox(frame=sampled_frame, bboxes=bboxes)
output = db.sinks.Column(columns={'frame': out_frame})
job = Job(op_args={
    frame: input_table.column('frame'),
    sampled_frame: sampler_args,
    bboxes: bboxes_table.column('bboxes'),
    output: movie_name + '_bboxes_overlay',
})
[out_table] = db.run(output=output, jobs=[job], force=True)
out_table.column('frame').save_mp4(movie_name + '_faces')

print('Successfully generated {:s}_faces.mp4'.format(movie_name))
