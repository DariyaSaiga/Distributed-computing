# Distributed-computing — Lab 1: RPC (JSON over TCP) on AWS EC2

Simple RPC client/server using **TCP sockets** and **JSON** messages.  
The client sends a request with `request_id`, `method`, and `params`. The server executes the method and returns a JSON response. The server logs every request.

---

## Requirements
- Two EC2 instances (Ubuntu 22.04):
  - `rpc-server-node`
  - `rpc-client-node`
- Server Security Group inbound rules:
  - **TCP 22** (SSH)
  - **TCP 5000** (RPC)

---

## Install (both machines)
```bash
sudo apt update
sudo apt install python3 python3-pip -y
```

---

## Run server (on `rpc-server-node`)
```bash
python3 server.py --port 5000
```

---

## Run client (on `rpc-client-node`)
Replace `<SERVER_PUBLIC_IP>` with your server public IP.

```bash
python3 client.py 54.221.54.174 --port 5000 --method add --a 5 --b 7
python3 client.py 54.221.54.174 --method reverse --s "Distributed"
```

Expected response example:
```json
{"request_id":"...","result":12,"status":"OK"}
```

---

## Failure demo (server delay + client retries)
### Server (artificial delay)
```bash
python3 server.py --port 5000 --delay 5
```

### Client (timeout triggers retries)
```bash
python3 client.py 54.221.54.174 --method add --a 1 --b 2 --timeout 2 --retries 3
```

---

## RPC message format
Request:
```json
{"request_id":"...","method":"add","params":{"a":5,"b":7},"timestamp":"..."}
```

Response:
```json
{"request_id":"...","result":12,"status":"OK"}
```

---

## RPC semantics (brief)
- Because the client retries on timeout, the system can behave as **at-least-once** (a request may be processed more than once).
- This implementation can deduplicate repeated requests using the same `request_id` (cached response), which approximates **at-most-once** while the server is running.
