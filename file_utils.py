import os, filelock

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