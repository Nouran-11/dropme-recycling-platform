import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("alert-sink")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            payload = json.loads(body)
            for alert in payload.get("alerts", []):
                log.info(
                    "alert status=%s name=%s severity=%s summary=%s",
                    alert.get("status"),
                    alert.get("labels", {}).get("alertname"),
                    alert.get("labels", {}).get("severity"),
                    alert.get("annotations", {}).get("summary"),
                )
            log.info("payload: %s", body.decode())
        except Exception as exc:
            log.error("bad payload: %s", exc)
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args) -> None:
        # Silence default request logging; alert payloads are logged above.
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
