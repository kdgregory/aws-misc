FROM python:3.13

RUN apt update && apt install -y vim

RUN useradd -m jupyter
USER jupyter

RUN pip install -U pip && pip install -U boto3 requests jupyterlab

WORKDIR /home/jupyter
RUN mkdir workspace 
COPY --chown=jupyter settings/ .jupyter/

CMD [ "/bin/bash", "-l", "-c", "jupyter lab" ]
