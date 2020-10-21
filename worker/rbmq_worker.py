import io, os, zipfile, shutil, json, filelock, pika, time
import numpy as np
import concurrent.futures

from functools import partial
from tempfile import NamedTemporaryFile
from timestamp_utils import add_timestamp_to_filename, get_timestamp_from_filename, remove_timestamp_from_filename
from PIL import Image
from threading import Semaphore
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from retry import retry

EXCHANGE = 'exchange'
QUEUE = 'exchage.reciever'

UPLOADS = '/tmp/uploads'
PROCESSED = '/tmp/processed'

WAIT_TIME = 1
HOST_IP = '172.17.0.1' # '127.0.0.1'
PORT = '5672'
MAX_WORKERS = 4
MULTI_THREAD = True
VALID_EXTENSIONS = ['jpg', 'png', 'zip']

semaphore = Semaphore(MAX_WORKERS)

def main():   
    global semaphore

    print('Waiting {}s before startup ...'.format(WAIT_TIME))
    time.sleep(WAIT_TIME)
    print('Connecting to server {}:{} ...'.format(HOST_IP, PORT))

    connection = connect()
    channel = setup_consume(connection)

    # don't consume if we don't have available workers
    while (True):
        if not MULTI_THREAD or semaphore._value > 0:
            try:
                print('Waiting for messages.')
                channel.start_consuming()
            except KeyboardInterrupt:
                channel.close()
                connection.close()
                break

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def connect():
    print("Setting up connection ...")
    try:
        creds = pika.PlainCredentials('guest', 'guest')
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=HOST_IP, port=PORT, credentials=creds))
    except Exception as e:
            print('Encountered error on worker startup: {}, attempting recovery'.format(repr(e)))

    return connection

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def setup_consume(connection, use_exchanges=True):
    print("Setting up channel ...")
    if connection is None:
        raise pika.exceptions.ConnectionWrongStateError

    channel = connection.channel()
    try:
        # we can keep the channel to the server open
        if use_exchanges:
            print("Setting up exchanges ...")
            channel = setup_exchanges(channel)
        else:
            channel.queue_declare(queue='task_queue', durable=True)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='task_queue', on_message_callback=callback)
            
    except Exception as e:
        print('Encountered error on worker consume: {}, attempting recovery'.format(repr(e)))
        if channel.is_open:
            channel.close()

    return channel

# add queue binding and extensions
def callback(ch, method, properties, body):
    global semaphore

    ch.basic_ack(delivery_tag=method.delivery_tag)

    extension = method.routing_key.split('_')[1]
    if len(body) > 0:
        f = None
        gry = None
        try:
            filename = add_timestamp_to_filename('receieved.' + extension)
            timestamp = get_timestamp_from_filename(filename)
            print("Got file {} as message".format(filename))

            print('Saving to local storage ...')
            path_to_file_upload = os.path.join(UPLOADS, filename)
            f = open(path_to_file_upload,'wb+')
            f.write(body)
            f.close()
            print('... Done!')

            if MULTI_THREAD:
                print('Processing in multi-threading mode ...')
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    try:
                        submitted = executor.submit(convert_to_greyscale_multi, filename.split('.')[0], extension, timestamp)
                    except:
                        semaphore.release()
                    else:
                        submitted.add_done_callback(lambda x: semaphore.release())
                
                file_loc = "{}/{}_gray.{}".format(PROCESSED, filename.split('.')[0], extension)
                print('Loading saved file {}...'.format(file_loc))

                print(os.path.exists(file_loc))
                gry = open(file_loc, "rb").read()
            else:
                gry = convert_to_greyscale(Image.open(f))
                ret_msg = io.BytesIO()
                ret_msg = gry.save(ret_msg, format=extension)
                gry = ret_msg.getvalue()

        except Exception:
            return 

        if gry is not None:
            print("Sending back grayscale file to exchange: server with routing key: server_{}...".format(extension))
            ch.basic_publish(
                exchange='server',
                routing_key='server_' + extension,
                body=gry,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ))

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def setup_exchanges(channel, mode='direct'):
    print('Setting up exchanges ...')
    # production exchange
    channel.exchange_declare(exchange='task', exchange_type=mode)

    # consumption exchange
    channel.exchange_declare(exchange='server', exchange_type=mode)

    for file_type in VALID_EXTENSIONS:
        # create and bind tasks queues
        channel.queue_declare(queue='task_' + file_type, durable=True)
        channel.queue_bind(queue='task_' + file_type, exchange='task')
        channel.basic_consume(queue='task_' + file_type, on_message_callback=callback)

    return channel

# converts an image to grayscale using averages
def convert_to_greyscale(img_mat):
    gry = np.average(np.asarray(img_mat), axis=-1)
    ret = Image.fromarray(gry).convert('RGB')
    return ret

# use tmp folders here
def convert_to_greyscale_multi(filename, extension, timestamp):     
    is_single_image = (extension != 'zip')

    # for zip
    image_files = []
    upload_filename = os.path.join(UPLOADS, filename+'.'+extension)
    processed_filename = "{}/{}_gray.{}".format(PROCESSED, filename, extension)
    if is_single_image:

        print('Single image {} encountered: converting to grayscale ...'.format(upload_filename))
        try:
            rgb = Image.open(upload_filename)
            gry = convert_to_greyscale(np.asarray(rgb))
            print('... Done!')
        except Exception as e:
            print("... Exception encountered while converting: {}".format(repr(e)))

        print('Saving as: {}...'.format(processed_filename))
        try:
            gry.save(processed_filename)
            print('... Done!')
        except Exception as e:
            print("... Exception encountered while saving: {}".format(repr(e)))
    else:
        # READ ZIP
        print('Zip {} encountered: converting to elements to grayscale ...'.format(upload_filename))

        try:
            with zipfile.ZipFile(upload_filename, "r") as zip_obj:
                # add timestamping to unzip files
                zip_files = zip_obj.namelist()

                for target_file in zip_files: 
                    print(' Processing file: {} ...'.format(target_file))
                    split_target = target_file.split(".")
                    target_name = split_target[0] + "_" + timestamp + "." + split_target[1]

                    if split_target[1] != 'jpg' and split_target[1] != 'png':
                        continue
                    
                    target_path = os.path.join(UPLOADS, target_name)
                    with open(target_path, "wb") as zf: 
                        zf.write(zip_obj.read(target_file)) 
                        rgb = Image.open(target_path)
                        gry = convert_to_greyscale(np.asarray(rgb))
                        processed_filename = "{}/{}_gray.{}".format(PROCESSED, target_name.split('.')[0], target_name.split('.')[1])

                        print(' Saving as: {} ...'.format(processed_filename))
                        gry.save(processed_filename)
                        image_files.append(processed_filename)
                    print(' ...Done')

                # write to zip
                processed_filename = os.path.join(PROCESSED, "{}_gray.{}".format(filename, extension))
                print("Writing new zipfile {} ...".format(processed_filename))
                try:
                    with zipfile.ZipFile(processed_filename, "w") as zip_obj:
                        for image_file in image_files:
                            raw_filename = image_file.split('/')[-1]
                            print(' Writing file {} ...'.format(raw_filename))

                            # write to zip
                            try:
                                zip_obj.write(os.path.join(PROCESSED, raw_filename), raw_filename)
                            except Exception as e:
                                print(' Exception encounterd: {}'.format(repr(e)))
                            print(' ...Done')
                except Exception as e:
                    print('Exception encounterd: {}'.format(repr(e)))
                print('...Done')

        except Exception as e:
            print('Exception encountered while processing zip: {}'.format(repr(e)))



if __name__ == '__main__':
     main()