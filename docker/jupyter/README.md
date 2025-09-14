Runs Jupyter Lab, with boto3 pre-installed.

To build:

```
docker build -t jupyter .
```

To run:

```
docker run -it --rm -u $(id -u):$(id -g) --network host \
           -v $(pwd):/home/jupyter/workspace \
           -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_DEFAULT_REGION -e AWS_REGION \
           jupyter:latest
```

Notes:

* When the container starts, it will print the URL for the lab server (a localhost address with token).
* If you create a notebook in the root of the workspace, it will be deleted when the container exits.
* The current working directory is mapped to the `workspace` directory in the container if you want to
  save your work.
* The "host" networking (versus a port mapping) allows multiple containers to run at the same time,
  using the same start command.
* AWS access is granted via environment variables. I consider this safer than mapping `$HOME/.aws`.
