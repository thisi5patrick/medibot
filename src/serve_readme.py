import http.server
import os
import socketserver
from pathlib import Path

import markdown

README_FILE = Path(__file__).resolve().parent.parent / "README.md"


class ReadMeHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with README_FILE.open("r", encoding="utf-8") as f:
                html_content = markdown.markdown(f.read())
                self.wfile.write(html_content.encode("utf-8"))
        else:
            self.send_error(404, "File not found")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    with socketserver.TCPServer(("", port), ReadMeHandler) as httpd:
        httpd.serve_forever()
