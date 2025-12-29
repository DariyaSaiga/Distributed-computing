#!/usr/bin/env python3
import argparse
import json
import socket
import time
from datetime import datetime

MAX_MSG = 1024 * 1024  # 1MB


def recv_line(conn: socket.socket) -> str:
    """Receive a single newline-terminated UTF-8 line."""
    buf = bytearray()
    while True:
        ch = conn.recv(1)
        if not ch:
            break
        if ch == b"\n":
            break
        buf += ch
        if len(buf) > MAX_MSG:
            raise ValueError("Message too large")
    return buf.decode("utf-8", errors="replace")


def send_json(conn: socket.socket, obj: dict) -> None:
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    conn.sendall(data)


def handle_method(method: str, params: dict):
    if method == "add":
        return int(params["a"]) + int(params["b"])
    if method == "reverse":
        return str(params["s"])[::-1]
    if method == "echo":
        return params
    raise ValueError(f"Unknown method: {method}")


def main():
    ap = argparse.ArgumentParser(description="Lab1 RPC Server (JSON over TCP)")
    ap.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    ap.add_argument("--port", type=int, default=5000, help="Port to listen on")
    ap.add_argument("--delay", type=float, default=0.0, help="Artificial delay before responding (seconds)")
    ap.add_argument("--drop_response", action="store_true", help="Simulate lost packet: do not send response")
    ap.add_argument("--no_dedupe", action="store_true", help="Disable request_id cache (at-least-once behavior)")
    args = ap.parse_args()

    # Dedup cache: request_id -> response (approx at-most-once while server is running)
    cache = {}

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.host, args.port))
        s.listen(50)
        print(f"[SERVER] Listening on {args.host}:{args.port} ({datetime.utcnow().isoformat()}Z)")

        while True:
            conn, addr = s.accept()
            with conn:
                try:
                    line = recv_line(conn)
                    if not line:
                        continue

                    req = json.loads(line)
                    request_id = req.get("request_id")
                    method = req.get("method")
                    params = req.get("params", {})

                    print(f"[SERVER] from {addr} req_id={request_id} method={method} params={params}")

                    if (not args.no_dedupe) and request_id in cache:
                        resp = cache[request_id]
                        print(f"[SERVER] duplicate req_id={request_id} -> cached response")
                    else:
                        if args.delay > 0:
                            time.sleep(args.delay)

                        result = handle_method(method, params)
                        resp = {
                            "request_id": request_id,
                            "result": result,
                            "status": "OK",
                            "server_time": datetime.utcnow().isoformat() + "Z",
                        }
                        if (not args.no_dedupe) and request_id:
                            cache[request_id] = resp

                    if args.drop_response:
                        print("[SERVER] drop_response enabled -> NOT sending reply (simulating loss)")
                        continue

                    send_json(conn, resp)

                except Exception as e:
                    err = {
                        "request_id": None,
                        "result": None,
                        "status": "ERROR",
                        "error": str(e),
                        "server_time": datetime.utcnow().isoformat() + "Z",
                    }
                    try:
                        send_json(conn, err)
                    except Exception:
                        pass
                    print(f"[SERVER] ERROR: {e}")


if __name__ == "__main__":
    main()
