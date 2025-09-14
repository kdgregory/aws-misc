#!/bin/bash
##
## Runs the Jupyter Lab container, passing AWS environment variables.
##

docker run -it --rm -u $(id -u):$(id -g) --network host \
           -v $(pwd):/home/jupyter/workspace \
           -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_DEFAULT_REGION -e AWS_REGION \
           jupyter:latest
