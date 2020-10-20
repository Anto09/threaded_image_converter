FROM python:3.8-alpine AS base

WORKDIR /app

RUN apk add -U --no-cache libffi-dev openssl-dev libmemcached-dev zlib-dev

# for numpy
RUN apk --no-cache add musl-dev linux-headers g++

# in the event that we want to build git repos from source
# RUN apk add -U --no-cache git gcc musl-dev make

# for pillow
RUN apk --update add build-base jpeg-dev zlib-dev

# Start compiling build code in another layer
FROM base AS build

COPY ./requirements.txt /app/requirements.txt


RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt
    
COPY . /app

# make temp file folders 
RUN mkdir tmp && cd tmp
RUN mkdir uploads && mkdir processed && cd ..

RUN ls -l

# run `python3 rbmq-worker.py`
ENTRYPOINT [ "python3" ]
CMD [ "rbmq_worker.py" ]

# alternative
# ADD rbmq_worker.py /
# CMD [ "python3", "./rbmq_worker.py" ]

