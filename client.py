#!/usr/bin/env python3
import argparse
import json
import socket
import time
import uuid
from datetime import datetime

MAX_MSG = 1024 * 1024  # 1MB


def recv_line(sock: socket.socket) -> str:
    buf = bytearray()
    while True:
        ch = sock.recv(1)
        if not ch:
            break
        if ch == b"\n":
            break
        buf += ch
        if len(buf) > MAX_MSG:
            raise ValueError("Message too large")
    return buf.decode("utf-8", errors="replace")


def rpc_once(host: str, port: int, payload: dict, timeout: float) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        line = recv_line(sock)
        if not line:
            raise TimeoutError("No response")
        return json.loads(line)


def main():
    ap = argparse.ArgumentParser(description="Lab1 RPC Client (JSON over TCP)")
    ap.add_argument("host", help="Server public IP or DNS")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--method", choices=["add", "reverse", "echo"], default="add")
    ap.add_argument("--a", type=int, default=5)
    ap.add_argument("--b", type=int, default=7)
    ap.add_argument("--s", type=str, default="hello")
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    request_id = str(uuid.uuid4())

    if args.method == "add":
        params = {"a": args.a, "b": args.b}
    elif args.method == "reverse":
        params = {"s": args.s}
    else:
        params = {"a": args.a, "b": args.b, "s": args.s}

    payload = {
        "request_id": request_id,
        "method": args.method,
        "params": params,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    last_err = None
    for attempt in range(1, args.retries + 1):
        try:
            print(f"[CLIENT] attempt {attempt}/{args.retries} req_id={request_id}")
            resp = rpc_once(args.host, args.port, payload, args.timeout)
            print("[CLIENT] response:", json.dumps(resp, ensure_ascii=False))
            return
        except Exception as e:
            last_err = e
            print(f"[CLIENT] error: {e}")
            if attempt < args.retries:
                time.sleep(0.5 * attempt)

    print(f"[CLIENT] FAILED after {args.retries} attempts. Last error: {last_err}")


if __name__ == "__main__":
    main()
