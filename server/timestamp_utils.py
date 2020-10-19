import re
from datetime import datetime

# add a timestamp to the filename
def add_timestamp_to_filename(filename):
    now = datetime.now()

    split_name = filename.split(".")
    return "{}_{}.{}".format(split_name[0], now.strftime("D%Y%m%dT%H%M%S%f"), split_name[1])

def get_timestamp_from_filename(filename):
    # split into name and extension
    split_name = filename.split(".")

    regex = r"D\d{8}T\d{12}"
    match = re.search(regex, split_name[0])

    return split_name[0][match.span()[0]:match.span()[1]]

# remove timestamp from a filename
def remove_timestamp_from_filename(filename):
    # split into name and extension
    split_name = filename.split(".")

    regex = r"_D\d{8}T\d{12}"
    match = re.search(regex, split_name[0])

    removed_timestamp_name = split_name[0][:match.span()[0]] + split_name[0][match.span()[1]:]
    return removed_timestamp_name + "." + split_name[1]

    # for no timestamps
    #return "_".join(split_name[0].split("_")[0:-1]) + "." + split_name[1]

def check_for_timestamp(filename, timestamp):
    split_name = filename.split(".")
    regex = r"{}".format(timestamp)

    return re.findall(regex, split_name) is not None