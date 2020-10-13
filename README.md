# threaded_image_converter
Simple script which using parallel processing to read images, convert them to grayscale, then right them back to the filesystem

# Usage
1. From the command line: 
- install requirements with `pip install -r requirements.txt`
- run `python threaded_greyscale_converter.py -s <source> -d <destination> -m <max workers for concurrency> -t <thread mode> -w <weights to be used for non-average greyscale converter>`
- source and destination are required and are absolute paths, the rest have default values
2. Running the notebook (ipynb):
- install necessary requirements 
- modify the inputs to final function call `batch_processing` and press play

# Recommendations:
1. `max_workers`: Running `cat /proc/cpuinfo | grep processor | wc -l` will display the number of cores available which will be your number of max_workers. For working on this I used half of that.