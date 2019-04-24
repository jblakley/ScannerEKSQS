# TODO: Remove v1-2? Tested with v3

import argparse

parser = argparse.ArgumentParser(description='Smoke Test Scanner QuickStart')
parser.add_argument('-v2', action='store_true',
                    help='Sequencial node id', default=False)

args = parser.parse_args()

if args.v2:
    from scannerpy import Database, DeviceType, Job
else:
    import scannerpy as scan

import os.path
import subprocess as sp

if __name__ == '__main__':
    example_video_path = 'star_wars_heros.mp4'

    if not os.path.isfile(example_video_path):
        print("File does not exist: %s" % example_video_path)
        outp = sp.check_output(
            '''
            wget https://storage.googleapis.com/scanner-data/tutorial_assets/star_wars_heros.mp4
            ''',
            shell=True).strip().decode('utf-8')
    else:
        print("Using: %s" % example_video_path)

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

    print('Connecting to Scanner database/client...')
    db = None
    if args.v2:
        db = Database(
            master=master,
            start_cluster=False,
            config_path='./config.toml',
            grpc_timeout=60)
    else:
        db = scan.Client(
            master=master,
            start_cluster=False,
            config_path='./config.toml',
            grpc_timeout=60)


    print('Running Scanner job...')
    # example_video_path = 'star_wars_heros.mp4'
    print(db.summarize())

    db.load_op("/opt/scanner/examples/tutorials/resize_op/libresize_op.so",
            "/opt/scanner/examples/tutorials/resize_op/resize_pb2.py")


    if args.v2:
        pass
        # TODO FIX or REMOVE
        # [input_table], _ = db.ingest_videos(
        #     [('example', example_video_path)], force=True, inplace=True)
         #
        # frame = db.sources.FrameColumn()
        # r_frame = db.ops.Resize(frame=frame, width=320, height=240)
        # output_op = db.sinks.Column(columns={'frame': r_frame})
        # job = Job(op_args={
        #     frame: db.table('example').column('frame'),
        #     output_op: 'example_frame'
        # })

        # output_tables = db.run(output=output_op, jobs=[job], force=True)
        #
        # output_tables[0].column('frame').save_mp4('resized_video')

    else:
        input_stream = scan.NamedVideoStream(db, 'example', path=example_video_path)

        frames = db.io.Input([input_stream])

        resized_frames = db.ops.MyResize(frame=frames, width=640, height=480)

        output_stream = scan.NamedVideoStream(db, 'example-resized')
        output = db.io.Output(resized_frames, [output_stream])
        db.run(output, scan.PerfParams.estimate(), cache_mode=scan.CacheMode.Ignore)

        output_stream.save_mp4('resized-video')

print(db.summarize())

print('Complete!')