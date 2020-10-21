import os, filelock

# delete with locking
def lock_delete(filepath, timeout=1, DEBUG=True):
    try:
        lock = filelock.FileLock(filepath+".lock")
        with lock.acquire(timeout=timeout):
                os.remove(filepath)
                lock.release()
    except Exception as e:
        if DEBUG:
            print("Lock-delete exception encountered: {}".format(repr(e)))
        return -1
    
    return 0

# check if the filename is a png, jpg, or zip (or whatever is in the config JSON)
def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

# check if the file is a zip file
def is_zip(filename):
    return filename.rsplit('.', 1)[1].lower() == "zip"