#!/usr/bin/env python3
"""
Cinema - Wisbyte Edition
Upload this as main.py to /home/container/
Put your video files in /home/container/films/
"""

import os
import json
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse

PORT = int(os.environ.get('PORT', 8080))

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv', '.wmv', '.ts', '.m2ts'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILMS_DIR = os.path.join(BASE_DIR, 'films')


def get_films():
    films = []
    if not os.path.isdir(FILMS_DIR):
        return films
    for filename in sorted(os.listdir(FILMS_DIR), key=lambda x: x.lower()):
        ext = os.path.splitext(filename)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            filepath = os.path.join(FILMS_DIR, filename)
            size_bytes = os.path.getsize(filepath)
            if size_bytes >= 1e9:
                size_str = f"{size_bytes / 1e9:.1f} GB"
            else:
                size_str = f"{size_bytes / 1e6:.0f} MB"
            name = os.path.splitext(filename)[0].replace('.', ' ').replace('_', ' ').strip()
            films.append({
                "filename": filename,
                "name": name,
                "size": size_str,
                "ext": ext[1:].upper()
            })
    return films


class CinemaHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  {self.address_string()} → {args[0]}")

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API: list films
        if path == '/api/films':
            films = get_films()
            body = json.dumps(films).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(body))
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)
            return

        # Serve video files with range support
        if path.startswith('/films/'):
            filename = unquote(path[7:])
            filepath = os.path.join(FILMS_DIR, filename)

            # Security: only serve files inside FILMS_DIR
            if not os.path.abspath(filepath).startswith(os.path.abspath(FILMS_DIR)):
                self.send_error(403)
                return

            if not os.path.isfile(filepath):
                self.send_error(404)
                return

            file_size = os.path.getsize(filepath)
            mime, _ = mimetypes.guess_type(filepath)
            if not mime:
                mime = 'video/mp4'

            range_header = self.headers.get('Range')

            if range_header:
                range_val = range_header.strip().replace('bytes=', '')
                parts = range_val.split('-')
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', length)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_cors()
                self.end_headers()

                with open(filepath, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', file_size)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_cors()
                self.end_headers()

                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            return

        # Serve index.html for everything else
        index_path = os.path.join(BASE_DIR, 'index.html')
        if os.path.isfile(index_path):
            with open(index_path, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "index.html not found")


if __name__ == '__main__':
    os.makedirs(FILMS_DIR, exist_ok=True)
    print(f"Cinema server starting on port {PORT}")
    print(f"Films folder: {FILMS_DIR}")
    films = get_films()
    print(f"Found {len(films)} film(s)")
    server = HTTPServer(('0.0.0.0', PORT), CinemaHandler)
    server.serve_forever()