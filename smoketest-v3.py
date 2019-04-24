
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


    input_stream = scan.NamedVideoStream(db, 'example', path=example_video_path)

    frames = db.io.Input([input_stream])

    resized_frames = db.ops.MyResize(frame=frames, width=640, height=480)

    output_stream = scan.NamedVideoStream(db, 'example-resized')
    output = db.io.Output(resized_frames, [output_stream])
    db.run(output, scan.PerfParams.estimate(), cache_mode=scan.CacheMode.Ignore)

    output_stream.save_mp4('resized-video')

    print(db.summarize())

    print('Complete!')