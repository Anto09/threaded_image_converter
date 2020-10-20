
import requests, os, zipfile, shutil, json, platform, filelock, pika, time, threading
from functools import partial
from flask import Flask, render_template, request, redirect, url_for, flash, send_file,send_from_directory, after_this_request
from werkzeug.utils import secure_filename
from tempfile import NamedTemporaryFile

from timestamp_utils import add_timestamp_to_filename, get_timestamp_from_filename, remove_timestamp_from_filename
from file_utils import lock_delete, allowed_file, is_zip
from retry import retry

WAIT_TIME = 1
HOST_IP = '172.17.0.1' # '127.0.0.1'
PORT = '5672'

filename_queue = []
return_queue = []
connection = None
channel = None

# create app with a loaded config
def create_app():
    app = Flask('file uploader server')
    app.config.from_json("upload_server_config.json")

    print("---Setting up app---")
    print(app.config)
    print("--------------------")
    return app

app = create_app()
app.secret_key = b"[-jA_AnvyG]|>*T"


def main():
    global connection, channel

    print('Waiting {}s before startup ...'.format(WAIT_TIME))

    print('Setting up rabbitmq connection ...')
    connection = connect()
    # channel = setup_consume(connection)

    
    # channel.basic_consume(queue='server_queue', on_message_callback=callback, auto_ack=True)
    # with app.app_context():
    #    while status.method.message_count > 0:
    #        print("consuming")
    #        method, properties, body = channel.basic_get('server_queue', auto_ack=True)
    #        callback(channel, method, properties, body)
            # channel.start_consuming()

    #consume_thread = threading.Thread(target=consume)
    #consume_thread.start()

    print('Starting app ...')
    app.run(host='0.0.0.0', debug=True)


# home route
@app.route("/")
def index():
    return render_template("index.html")

# route for uploading the file (should probably get rid of GET)
@app.route("/upload_file", methods=["GET", "POST"])
def upload_file():
    global channel, filename_queue

    # check for valid uploads, exit and flash warning if invalid
    if "file" not in request.files:
        flash("No file in request")
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        flash("No selected file")
        return redirect(url_for("index"))

    if file.filename.split('.')[1] != 'jpg':
        flash("Invalid file extension: can only accept jpgs (for now...  (._. ) )")
        return redirect(url_for("index"))

    if file is not None:
        print("Got file: {}".format(file.filename))
        filename_queue.append(file.filename)

        file.stream.seek(0)
        msg = file.stream.read()

        print("Sending file to worker ...")
        channel = connection.channel()
        channel.basic_publish(
            exchange='',
            routing_key="task_queue",
            body=msg)
            
        # channel = setup_consume(channel)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='server_queue', on_message_callback=callback, auto_ack=True)
        channel.start_consuming()

        if len(return_queue) > 0:
            print('Sending back file')
            # should we close channel?
            # ch.close()
            if len(filename_queue) > 0:
                # send back all jpgs for now
                new_filename_split = filename_queue.pop(0).split('.')
                new_filename = new_filename_split[0] + '_gray' + '.jpg'

                return send_file(return_queue.pop(0), as_attachment=True, attachment_filename=new_filename)
            else:
                return send_file(return_queue.pop(0), as_attachment=True, attachment_filename='temp_gray.jpg')

    return redirect(url_for("index"))

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
def setup_consume(channel):
    if channel is None:
        raise pika.exceptions.ChannelError
    
    try:
        channel.queue_declare(queue="server_queue", durable=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='server_queue', on_message_callback=callback, auto_ack=True)

    except Exception as e:
        print('Encountered error on server consume: {}'.format(repr(e)))
        channel.close()

    return channel

def consume():
    global connection, channel

    while connection is not None and channel is not None and connection.is_open() and channel.is_open():
        channel.start_consuming()

def callback(ch, method, properties, body):
    global return_queue

    print("Got worker response")
    
    if len(body) > 0:
        
        # worry about zip files and renaming later
        f = open('received_image.jpg','wb+')
        f.write(body)
        f.seek(0, 0)
            
        return_queue.append(f)
        ch.close()

if __name__ == "__main__":
    main()