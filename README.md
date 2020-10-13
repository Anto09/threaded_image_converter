# threaded_image_converter
Simple script which using parallel processing to read images, convert them to grayscale, then right them back to the filesystem

This application uses Python 3's concurrent.futures.ThreadPoolExecutor to spawn multiple workers which:
1. Read the image file into main memory (from a specified directory)
2. Use numpy to convert the image to grayscale
3. Save the image back to a destination directory

## Arguments:
1. `source` (REQUIRED, `str`): source image folder, must be an absolute path
2. `destination` (REQUIRED, `str`): destination image folder, must be an absolute path. Application will attempt to create the folder if it does not exist
3. `max_workers` (OPTIONAL, `int`): Running `cat /proc/cpuinfo | grep processor | wc -l` will display the number of cores available which will be your number of max_workers. Defaults to value of 4.
4. `thread` (OPTIONAL, `str`): Thread mode; can either be `single` or `multi`. Defaults to `multi`
5. `weights` (OPTIONAL, `str`): Weights to be used for non-average grayscaling. Must be a 3-element numpy vector, corresponding to the RGB weights, in string format (`[r, g, b]`). Defaults to `None`.

## Usage
1. From the command line: 
- install requirements with `pip install -r requirements.txt`
- run `python threaded_greyscale_converter.py -s <source> -d <destination> -m <max_workers> -t <thread> -w <weights>`
2. Running the notebook (ipynb):
- install necessary requirements 
- modify the inputs to final function call `batch_processing` and press play
3. Sample output:
```
Operating in multi-threaded mode
Grabbing images from: /home/antonioumali/Desktop/Experiments/Python-Experiments/lfw
Saving images to: /home/antonioumali/Desktop/Experiments/Python-Experiments/lfw-grayscale
Using None value for weights
Processing 13233 files in multi-threaded mode...
Using 4 workers...
--- Mode multi took 24.600640296936035 seconds ---
Successfully converted 13233 image!
```