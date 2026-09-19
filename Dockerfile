# Dockerfile - Python 3.13 svcdesk image (based on Dockerfile.example).
# Dependencies are installed at BUILD time (the grader's sandbox has no network once the image is built);
# the service listens on port 8080 inside the container.
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
