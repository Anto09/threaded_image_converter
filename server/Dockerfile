FROM python:3.8-alpine AS base
WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Start compiling build code in another layer
FROM base AS build

COPY ./requirements.txt /app/requirements.txt

RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt
    
# Create a slim image which only contains the entrypoint and the python packages
# FROM base AS slim

COPY . /app

EXPOSE 5000

# run `python3 rbmq-server.py`
ENTRYPOINT [ "python3" ]

CMD [ "rbmq_server.py" ]