# syntax=docker/dockerfile:1

FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0

# Static assets only — no build step, no node_modules. The base image already
# runs as a non-root user and listens on 8080.
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/app.js /usr/share/nginx/html/app.js

EXPOSE 8080

# 127.0.0.1, not localhost: busybox wget tries only the first resolved address,
# and localhost resolves to ::1 while nginx listens on IPv4.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/"]
