# Dockerfile - Python 3.13 svcdesk image (based on Dockerfile.example).
# Dependencies are installed at BUILD time (the grader's sandbox has no network once the image is built);
# the service listens on port 8080 inside the container.
#
# Lab 5 triage: the base image is pinned by digest (a floating tag silently ages), the OS packages are
# upgraded inside the image, and pip is removed at the end of the build - it is needed only to install,
# and Trivy reports fixable HIGH/CRITICAL vulnerabilities in the copies pip vendors (pip/_vendor).
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && pip uninstall -y pip

COPY src/ /app/src/

RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
