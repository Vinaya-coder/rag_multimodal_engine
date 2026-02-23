FROM ubuntu:latest
LABEL authors="vinaya"

ENTRYPOINT ["top", "-b"]