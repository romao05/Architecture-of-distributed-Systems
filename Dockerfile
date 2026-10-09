FROM python:3.9-slim-bookworm
RUN apt-get update
# Install rpyc, redis for caching, and data libraries for the benchmark plots
RUN pip3 install rpyc redis matplotlib numpy
CMD [ "/bin/bash", "-c", "while true; do bash -l; done" ]