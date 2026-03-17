#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$(pwd)

python app/worker/submit_worker.py &

python app/worker/communicate_worker.py &

uvicorn app.main:app --host 0.0.0.0 --port 10000 --proxy-headers