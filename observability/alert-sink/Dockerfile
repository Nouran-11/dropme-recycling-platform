# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

RUN useradd --system --uid 10002 app
COPY observability/alert-sink/app.py /app/app.py
USER 10002
EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=3s --start-period=3s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:9000/').status==200 else 1)"]

CMD ["python", "/app/app.py"]
