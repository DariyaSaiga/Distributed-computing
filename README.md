# Distributed-computing

# Lab 1 — RPC (JSON over TCP) on AWS EC2

## Requirements
- Two EC2 instances (Ubuntu 22.04):
  - rpc-server-node
  - rpc-client-node
- Server Security Group inbound:
  - TCP 5000 (for RPC)
  - TCP 22 (SSH)

## Install (both machines)
sudo apt update
sudo apt install python3 python3-pip -y

## Run server (on rpc-server-node)
python3 server.py --port 5000

## Run client (on rpc-client-node)
python3 client.py 54.221.54.174 --port 5000 --method add --a 5 --b 7
python3 client.py 54.221.54.174 --method reverse --s "Distributed"

## Failure demo (server delay)
Server:
python3 server.py --port 5000 --delay 5

Client (timeout triggers retries):
python3 client.py 54.221.54.174 --method add --a 1 --b 2 --timeout 2 --retries 3

## Message format
Request:
{"request_id":"...","method":"add","params":{"a":5,"b":7},"timestamp":"..."}

Response:
{"request_id":"...","result":12,"status":"OK"}
