# Use Ubuntu base image
FROM ubuntu:22.04

# Update package list and install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg

# Install pip
RUN apt-get install -y python3-pip

# Copy requirements.txt and install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Set working directory
WORKDIR /app

COPY loadmodels.py /app/loadmodels.py

RUN python3 /app/loadmodels.py

# Copy transcribebot.py
COPY transcribebot.py /app/transcribebot.py


# Run transcribebot.py
CMD ["python3", "transcribebot.py"]
