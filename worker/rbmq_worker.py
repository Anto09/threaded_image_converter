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
MULTI_THREAD = False
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
        image_files = []
        is_single_image = extension != 'zip'
        try:
            if is_single_image:
                filename = add_timestamp_to_filename('received_image.jpg')
                print("Got file {} as message".format(filename))

                f = open(filename,'wb+')
                f.write(body)
                image_files.append(f)

        except Exception:
            return 

        ret_msg = "Empty"
        if MULTI_THREAD:
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                try:
                    for image in image_files:
                        semaphore.acquire()
                        
                        # convert 
                        submitted = executor.submit(convert_to_greyscale_multi, image)

                        # change this later
                        ret_msg = "returning"
                except:
                    semaphore.release()
                else:
                    submitted.add_done_callback(lambda x: semaphore.release())
        else:
            gry = convert_to_greyscale(Image.open(f))

            ret_msg = io.BytesIO()
            gry.save(ret_msg, format='JPEG')
        
        # Save file
        gry.save("{}/{}_gray.{}".format(PROCESSED, add_timestamp_to_filename('image'), 'jpg'))

        print("Sending back grayscale file to exchange: server with routing key: server_{}...".format(extension))
        ch.basic_publish(
            exchange='server',
            routing_key='server_' + extension,
            body=ret_msg.getvalue(),
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
    return Image.fromarray(gry).convert('RGB')

# use tmp folders here
def convert_to_greyscale_multi(img_mat):
    pass


if __name__ == '__main__':
     main()