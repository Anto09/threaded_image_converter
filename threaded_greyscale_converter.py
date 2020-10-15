import os, sys, time
import numpy as np
import concurrent.futures
import argparse
import asyncio

from os.path import join, isfile
from PIL import Image
from threading import BoundedSemaphore
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

# command line arguments
ap = argparse.ArgumentParser()
ap.add_argument("-s", "--source", help="source folder; provide absolute path", type=str)
ap.add_argument("-d", "--destination", help="destination folder; provide absolute path", type=str)
ap.add_argument("-m", "--max_workers", help="number of workers to use for multi-threading", type=int, default=4)
ap.add_argument("-t", "--thread", help="single or multi", type=str, default="multi")
ap.add_argument("-w", "--weights", help="grayscale with weights vs average(default)", type=str, default=None)
args = vars(ap.parse_args())

# converts an image to grayscale using either averages or weights (for rgb weight sum)
def convert_to_greyscale(img_mat, use_avg=True, weights=np.array([0.21, 0.72, 0.07])):
    if use_avg:
        return np.average(img_mat, axis=-1)
    elif weights is not None:
        return np.dot(img_mat[...,:3], weights)

# Use ThreadPoolExecutor on this function
def load_convert_save_image(src, img, dest, weights):
    try:
        rgb = Image.open(join(src, img))

        # figure out if convert function will be using averaging or not
        # if weights are present check if default weights are to be used
        if weights is not None:
            if weights == "default":
                grayscale = Image.fromarray(convert_to_greyscale(np.asarray(rgb), use_avg=False))
            else:
                grayscale = Image.fromarray(convert_to_greyscale(np.asarray(rgb), use_avg=False, weights=weights))

        else:
            grayscale = Image.fromarray(convert_to_greyscale(np.asarray(rgb), use_avg=True))

        # split image name from extension so _gray can be appended to the name
        img_name = img.split(".")[0]
        extension = img.split(".")[1]

        # make sure all image values are from 0-255 before saving using the same image name but wwith _gray appended
        grayscale.convert('RGB').save("{}/{}_gray.{}".format(dest, img_name, extension))

        return 0

    except Exception as e:
        print("Exception encountered while converting to greyscale: {}".format(repr(e)))
        return -1

### Serial or multithreaded batch image processing
def batch_processing(src, dest, mode="single", max_workers=4, bound=100, weights=None):
    # check if source directory exists
    if not os.path.exists(src):
        print("Source directory does not exist")
        return

    # extract all files 
    files = [f for f in os.listdir(src) if isfile(join(src, f))]

    # clean image files; don't consider anything that's not a png or jpg file
    image_files = []
    for image in files:
        if "jpg" not in image and "png" not in image:
            continue
        else:
            image_files.append(image)

    # check if destination directory exists, attempt to create if it does not
    if not os.path.exists(dest):
        print("Destination directory does not exist, attempting to create...")
        try:
            os.makedirs(dest)
        except OSError as e:
            print ("Creation of the directory {} failed: {}".format(dest, repr(e)))
            return 

    # if weights are provided try to convert them from string array to np array, otherwise flag for use of default weights
    if weights is not None:
        try:
            weights = np.fromstring(weights)
        except Exception:
            weights = "default"

    # print some information
    print("Operating in {}-threaded mode".format(mode))
    print("Grabbing images from: {}".format(src))
    print("Saving images to: {}".format(dest))
    print("Using {} value for weights".format(weights))
    print("Processing {} files in {}-threaded mode...".format(len(image_files), mode))


    # initialize performance metrics
    start_time = time.time()
    convert_sucess = 0
    
    # enter single threaded (serial) mode
    if mode == "single": 
        for image in image_files:
            # returns 1 or 0; if 0 -> success, add to success count
            res = load_convert_save_image(src, image, dest, weights)
            if res == 0:
                convert_sucess += 1

    # enter multi threaded (serial) mode
    elif mode == "multi":
        print("Using {} workers...".format(max_workers))

        executed = set()

        semaphore = BoundedSemaphore(bound + max_workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

            if bound > 0: 
                semaphore.acquire()

                for image in image_files:
                    try:
                        submitted = executor.submit(load_convert_save_image, src, image, dest, weights)
                        res = submitted.result()
                        if res == 0:
                            convert_sucess += 1
                    except:
                        semaphore.release()
                        print("Exception encountered: {}".format(repr(e)))
                    else:
                        submitted.add_done_callback(lambda x: semaphore.release())
                        executed.add(submitted)

            else:
                # submit function extract_single_image with image_rul as the argument
                
                executed = {executor.submit(load_convert_save_image, src, image, dest, weights) for image in image_files}

                for future in concurrent.futures.as_completed(executed):
                    try:
                        # returns 1 or 0; if 0 -> success, add to success count
                        res = future.result()
                        if res == 0:
                            convert_sucess += 1
                    except Exception as e:
                        print("Exception encountered: {}".format(repr(e)))

    # print total execution time (for comparison)
    print("--- Mode {} took {} seconds ---".format(mode, time.time() - start_time))

    # print total conversion success count
    print("Successfully converted {} images!".format(convert_sucess))

if __name__ == "__main__":
    batch_processing(args.get("source"), args.get("destination"), mode=args.get("thread", "multi"), max_workers=args.get("max_workers", 4), weights=args.get("weights", None))