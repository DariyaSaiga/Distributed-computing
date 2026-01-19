# Distributed Computing — Lab 3: Raft Lite (Leader Election + Log Replication) on AWS EC2

This lab implements a **Raft Lite** cluster with:
- **Leader election** (Follower → Candidate → Leader)
- **Heartbeat** messages (leader periodically contacts followers)
- **Log replication** (`SET key=value` commands)
- **Majority commit** (entry is committed after a majority of nodes acknowledge)

> **IMPORTANT:** All files for **Lab 3** are located in the folder **`Lab3/`**.

---

## Requirements
- **Three EC2 instances** (Ubuntu 22.04), same VPC:
  - `node-A`
  - `node-B`
  - `node-C`
- **Security Group inbound rules**
  - TCP **22** (SSH)
  - TCP **8000-8002** (Raft HTTP RPC between nodes)
  - Recommended: source = **the same Security Group** (VPC-only traffic)

---

## Install (run on all 3 machines)
```bash
sudo apt update
sudo apt install -y python3 python3-pip
```

---

## Files (Lab3/)
Typical contents:
- `node.py` — Raft Lite node (HTTP JSON endpoints)
- (optional) `client.py` or use `curl` as client

---

## Deployment (use PRIVATE IPs inside the VPC)
Find each instance **private IP** (example format `172.31.x.x`) and run one node per instance.

### Run Node A (on instance A)
```bash
python3 -u node.py --id A --port 8000 --peers <B_PRIVATE_IP>:8001,<C_PRIVATE_IP>:8002
```

### Run Node B (on instance B)
```bash
python3 -u node.py --id B --port 8001 --peers <A_PRIVATE_IP>:8000,<C_PRIVATE_IP>:8002
```

### Run Node C (on instance C)
```bash
python3 -u node.py --id C --port 8002 --peers <A_PRIVATE_IP>:8000,<B_PRIVATE_IP>:8001
```

Expected startup log:
```text
[Node A] Listening on 0.0.0.0:8000 peers=['<B_PRIVATE_IP>:8001', '<C_PRIVATE_IP>:8002']
```

---

## Part 1 — Leader Election (Required)
Behavior:
- Nodes start as **Followers**
- If no heartbeat is received within a timeout → node becomes **Candidate**, increments term, requests votes
- Node becomes **Leader** when it receives a **majority** of votes
- Leader sends periodic **heartbeats**

Example logs:
```text
[Node B] Timeout -> Candidate (term 3)
[Node B] Received votes -> Leader (term 3)
[Leader B] Heartbeat (term 3)
```

---

## Part 2 — Log Replication (Required)
Client sends commands to the **leader**, for example:
- `SET x=5`

### Send command to leader (use curl from any EC2 in the VPC)
Try the current leader first (example: Node A on `<A_PRIVATE_IP>:8000`):
```bash
curl -sS -X POST http://<A_PRIVATE_IP>:8000/client_command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"SET x=5"}'
```

If you get `"Not leader"`, send the same request to the other node ports (8001 / 8002).

Required logs (example):
```text
[Leader A] Append log entry (term=3, cmd=SET x=5)
[Node C] Append success
[Leader A] Entry committed (index=0)
```

---

## Part 3 — Failure Experiment (REQUIRED)

### Scenario A — Leader crash (recommended)
1. Start cluster and observe leader election
2. **Kill leader process** (Ctrl+C on leader terminal)
3. Observe **new leader election**
4. Submit a new command successfully:
```bash
curl -sS -X POST http://<NEW_LEADER_PRIVATE_IP>:<PORT>/client_command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"SET z=9"}'
```

(Scenario B — follower crash is also acceptable if shown in the report.)

---

## Communication (Message passing)
Nodes communicate using **HTTP + JSON**:
- `POST /request_vote` → `{"term":..., "voteGranted":...}`
- `POST /append_entries` → `{"term":..., "success":...}`
- `POST /client_command` → leader appends + replicates

---

## Report / Screenshots (what to capture)
Minimum recommended screenshots:
1. **Startup**: 3 terminals with `Listening...`
2. **Leader election**: `Timeout -> Candidate` and `... -> Leader`
3. **Heartbeat**: `[Leader X] Heartbeat ...`
4. **Log replication**: `Append log entry`, follower `Append success`, leader `Entry committed`
5. **Failure**: kill leader, new leader election, new command succeeds



