
import requests, os, zipfile, shutil, json, platform, filelock, pika
from functools import partial
from flask import Flask, render_template, request, redirect, url_for, flash, send_file,send_from_directory, after_this_request
from werkzeug.utils import secure_filename
from tempfile import NamedTemporaryFile

from timestamp_utils import add_timestamp_to_filename, get_timestamp_from_filename, remove_timestamp_from_filename
from file_utils import lock_delete, allowed_file, is_zip

# create app with a loaded config
def create_app():
    app = Flask('file uploader server')
    app.config.from_json("upload_server_config.json")

    print(app.config)
    return app

app = create_app()
app.secret_key = b"[-jA_AnvyG]|>*T"

# home route
@app.route("/")
def index():
    return render_template("index.html")

# route for uploading the file (should probably get rid of GET)
@app.route("/upload_file", methods=["GET", "POST"])
def upload_file():
    
    file = request.files["file"]
    file.stream.seek(0)
    msg = file.stream.read()

    print(type(msg))


    creds = pika.PlainCredentials('guest', 'guest')
    # params = pika.ConnectionParameters('127.0.0.1', 5672, '/', creds)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='127.0.0.1', port=5672, credentials=creds))
    channel = connection.channel()

    channel.queue_declare(queue="server_queue", durable=True)
    channel.basic_publish(
        exchange='',
        routing_key="task_queue",
        body=msg)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='server_queue', on_message_callback=callback)
    channel.start_consuming()
    connection.close()
            
            
    return redirect(url_for("index"))

def callback(ch, method, properties, body):

    f = open('received_image.jpg','wb+')
    f.write(body)
        
    print(f)

    ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.close()


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)