#!/bin/bash
# Start Jupyter notebook in docker mounting current folder with ipynb file.

echo "Starting Jupyter in Docker mounting current folder inside container."
echo "It will be available at http://localhost:8888 address."

docker run -d -p 8888:8888 --name jupyter -v $(pwd):/home/jovyan/work jupyter/scipy-notebook
sleep 5
open http://localhost:8888