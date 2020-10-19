import requests, io, os, zipfile, shutil, json, filelock, pika, time
from functools import partial
from flask import Flask, request
from tempfile import NamedTemporaryFile

from timestamp_utils import add_timestamp_to_filename, get_timestamp_from_filename, remove_timestamp_from_filename
from file_utils import lock_delete, allowed_file, is_zip
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

EXCHANGE = 'exchange'
QUEUE = 'exchage.reciever'

UPLOADS = 'tmp/uploads'
PROCESSED = 'tmp/processed'

def main():   
    print(' [*] Connecting to server ...')
    try:
        creds = pika.PlainCredentials('guest', 'guest')
        # params = pika.ConnectionParameters('127.0.0.1', 5672, '/', creds)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='127.0.0.1', port=5672, credentials=creds))
        channel = connection.channel()
        channel.queue_declare(queue='task_queue', durable=True)
        print(' [*] Waiting for messages.')


        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='task_queue', on_message_callback=callback)
    except Exception as e:
            print('Encountered error on worker startup: {}'.format(repr(e)))

    while (True):
        try:
            channel.start_consuming()
        except Exception as e:
            print('Encountered error on worker consume: {}'.format(repr(e)))
            channel.close()
            break

def callback(ch, method, properties, body):
        if len(body) == 0:
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            filename = add_timestamp_to_filename('received_image.jpg')
            f = open(filename,'wb+')
            f.write(body)
            
            print("Got file {} as message".format(filename))

            # basic 
            rgb = Image.open(f)
            gry = Image.fromarray(convert_to_greyscale(np.asarray(rgb))).convert('RGB')

            # use batch processing (how to include zip files?)

            ret_msg = io.BytesIO()
            gry.save(ret_msg, format='JPEG')

            ch.basic_ack(delivery_tag=method.delivery_tag)
            ch.basic_publish(
                exchange='',
                routing_key='server_queue',
                body=ret_msg.getvalue(),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ))

# converts an image to grayscale using averages
def convert_to_greyscale(img_mat):
    return np.average(img_mat, axis=-1)



if __name__ == '__main__':
     main()