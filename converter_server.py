import requests, os, zipfile, shutil, json, platform, filelock
from flask import Flask, render_template, request, redirect, url_for, flash, send_file,send_from_directory, after_this_request
from werkzeug.utils import secure_filename
from threaded_greyscale_converter import batch_processing
from tempfile import NamedTemporaryFile

from timestamp_utils import add_timestamp_to_filename, get_timestamp_from_filename, remove_timestamp_from_filename
from file_utils import lock_delete

# create app with a loaded config
def create_app():
    app = Flask('file uploader server')
    app.config.from_json("upload_server_config.json")

    print(app.config)
    return app

app = create_app()
app.secret_key = b"[-jA_AnvyG]|>*T"

# check if the filename is a png, jpg, or zip (or whatever is in the config JSON)
def allowed_file(filename):
    print(app.config["VALID_EXTENSIONS"])
    print(filename.rsplit('.', 1)[1].lower())
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["VALID_EXTENSIONS"]

# check if the file is a zip file
def is_zip(filename):
    return filename.rsplit('.', 1)[1].lower() == "zip"

# home route
@app.route("/")
def index():
    return render_template("index.html")

# route for uploading the file (should probably get rid of GET)
@app.route("/upload_file", methods=["GET", "POST"])
def upload_file():

    if request.method == 'POST':

        file = request.files["file"]

        # check for valid uploads, exit and flash warning if invalid
        if "file" not in request.files:
            flash("No file in request")
            return redirect(url_for("index"))

        if file.filename == "":
            flash("No selected file")
            return redirect(url_for("index"))

        if not allowed_file(file.filename):
            flash("Invalid file extension")
            return redirect(url_for("index"))

        print("Posted file: {}".format(request.files["file"]))
        
        # files = {'file': file.read()}
        # for read_file in files:
        #     print(read_file)

        # store filename and upload directory
        stamped_filename = add_timestamp_to_filename(file.filename)
        path_to_file_upload = os.path.join(app.config["UPLOAD_FOLDER"], stamped_filename)
        file.stream.seek(0)
        file.save(path_to_file_upload)

        src = os.path.join(os.getcwd(), app.config["UPLOAD_FOLDER"])
        dest = os.path.join(os.getcwd(), app.config["PROCESSED_FOLDER"])

        # get all zip file names and extract them to the upload folder
        zip_files = []
        stamped_zipped_filenames = []
        
        if is_zip(stamped_filename):
            with zipfile.ZipFile(path_to_file_upload, "r") as zip_obj:
                # zip_obj.extractall(src)

                # add timestamping to unzip files
                zip_files = zip_obj.namelist()
                zip_timestamp = get_timestamp_from_filename(stamped_filename)
                for target_file in zip_files: 

                    split_target = target_file.split(".")
                    target_name = split_target[0] + "_" + zip_timestamp + "." + split_target[1]

                    stamped_zipped_filenames.append(target_name)
                    target_path = os.path.join(src, target_name)
                    with open(target_path, "wb") as f: 
                        f.write(zip_obj.read(target_file)) 

        # initialize greyscale converter pipeline
        weights = app.config["PROCESSED_FOLDER"]
        if weights == "None":
            weights = None

        print("Processing...")

        # process uploads
        batch_processing(src=src,
                         dest=dest,
                         mode=app.config["MODE"],
                         max_workers=app.config["WORKERS"],
                         weights=weights)

        print("Done")

        # empty tmp upload directory (if required)
        try:
            if app.config["DELETE_UPLOADS"]:
                if is_zip(stamped_filename):
                    for zip_file in stamped_zipped_filenames:
                        lock_delete(os.path.join(src, zip_file))
                
                lock_delete(path_to_file_upload)

        except Exception as e:
            print("Encountered error deleting files: {}".format(repr(e)))

        print("Sending files...")
        # send the files automatically
        try:
            if is_zip(stamped_filename):
                new_zip = stamped_filename.split(".")[0] + "_gray" + "." + stamped_filename.split(".")[1]

                # return redirect(url_for("get_zip", zip_filename=new_zip, images=zip_files))
                # add timestamp to zip
                return redirect(url_for("get_zip", zip_filename=new_zip, images=stamped_zipped_filenames))
            else:
                # just return single files
                img_name = stamped_filename.split(".")[0]
                extension = stamped_filename.split(".")[1]

                processed_filename = "{}_gray.{}".format(img_name, extension)
                return redirect(url_for("get_image", image_filename=processed_filename))
        except Exception as e:
            exception_msg = "Exception encountered: {}".format(repr(e))
            print(exception_msg)
            flash(exception_msg)
            return redirect(url_for("index"))


# make a route just in case auto delete is turned off and you want to retrieve a processed picture
@app.route("/get_image/<image_filename>",methods = ["GET","POST"])
def get_image(image_filename):
    dest = os.path.join(os.getcwd(), app.config["PROCESSED_FOLDER"])

    print("Sending back image {}...".format(image_filename))

    if app.config["DELETE_PROCESSED"]:
        try: 
            # copy image into a temporary file so we can close the file reader, delete our file, and still send our temp image
            temp_image = NamedTemporaryFile(mode="w+b",suffix=image_filename.split(".")[1])
            image_file_handle = open(os.path.join(dest, image_filename), "rb")
            shutil.copyfileobj(image_file_handle, temp_image)
            image_file_handle.close()
            temp_image.seek(0,0)

            # delete processed image
            lock_delete(os.path.join(dest, image_filename))

            try:
                return send_file(temp_image, as_attachment=True, attachment_filename=remove_timestamp_from_filename(image_filename))
            except FileNotFoundError:
                return "404 File not found"
        except Exception as e:
            return "Exception {} encountered".format(repr(e))
    else:
        return send_from_directory(dest, image_filename, as_attachment=True, attachment_filename=remove_timestamp_from_filename(image_filename))

# make a route just in case auto delete is turned off and you want to retrieve a bunch of processed pictures
@app.route("/get_zip/",methods = ["GET","POST"])
def get_zip():
    zip_filename = request.args["zip_filename"]
    print("Sending back zip {}...".format(zip_filename))
    images = request.args.getlist("images")
    dest = os.path.join(os.getcwd(), app.config["PROCESSED_FOLDER"])

    # write to zip
    with zipfile.ZipFile(os.path.join(dest, zip_filename), "w") as zip_obj:
        for zip_file in images:

            # reformat file name
            img_name = zip_file.split(".")[0]
            extension = zip_file.split(".")[1]

            image_filename = "{}_gray.{}".format(img_name, extension)

            # write to zip
            zip_obj.write(os.path.join(dest, image_filename), remove_timestamp_from_filename(image_filename))
    
            # delete if needed
            if app.config["DELETE_PROCESSED"]:
                lock_delete(os.path.join(dest, image_filename))

    # send and delete
    if app.config["DELETE_PROCESSED"]:
        try: 
            # copy zip into a temporary file so we can close the file reader, delete our file, and still send our temp zip
            temp_zip = NamedTemporaryFile(mode="w+b",suffix=".zip")
            zip_file_handle = open(os.path.join(dest, zip_filename), "rb")
            shutil.copyfileobj(zip_file_handle, temp_zip)
            zip_file_handle.close()
            temp_zip.seek(0,0)

            # delete processed zipfile
            lock_delete(os.path.join(dest, zip_filename))

            try:
                return send_file(temp_zip, as_attachment=True, attachment_filename=remove_timestamp_from_filename(zip_filename))
            except FileNotFoundError:
                return "404 File not found"
        except Exception as e:
            return "Exception {} encountered".format(repr(e))
    else:
        return send_from_directory(dest, zip_filename, as_attachment=True, attachment_filename=remove_timestamp_from_filename(zip_filename))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)