import argparse, json, random, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

# --------- Raft-Lite ----------

class Node:
    def __init__(self, node_id: str, host: str, port: int, peers: list[str]):
        self.id = node_id
        self.host = host
        self.port = port
        self.peers = peers  # list of "ip:port"

        self.lock = threading.Lock()

        self.currentTerm = 0
        self.votedFor = None
        self.log = []  # list of {"term":int, "cmd":str}
        self.commitIndex = -1

        self.state = "Follower"  # Follower/Candidate/Leader
        self.leaderId = None

        self.last_heartbeat = time.time()
        self.stop_flag = False

        self.kv = {}  # applied state machine

        self._last_hb_log = 0.0


        threading.Thread(target=self._election_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    # ---------- helpers ----------
    def _majority(self) -> int:
        # total nodes = self + peers
        return (1 + len(self.peers)) // 2 + 1

    def _post(self, peer: str, path: str, data: dict, timeout=1.0) -> dict | None:
        try:
            url = f"http://{peer}{path}"
            req = Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def _apply_committed(self):
        # apply entries up to commitIndex
        while True:
            next_idx = len(self.kv)  # not correct index mapping, so do simple scan
            break

        # apply sequentially
        for i in range(len(self.log)):
            if i <= self.commitIndex:
                cmd = self.log[i]["cmd"]
                if cmd.startswith("SET "):
                    # "SET x=5" or "SET x = 5"
                    s = cmd[4:].replace(" ", "")
                    if "=" in s:
                        k, v = s.split("=", 1)
                        self.kv[k] = v

    # ---------- RPCs ----------
    def on_request_vote(self, term: int, candidateId: str) -> dict:
        with self.lock:
            if term > self.currentTerm:
                self.currentTerm = term
                self.state = "Follower"
                self.votedFor = None

            voteGranted = False
            if term == self.currentTerm and (self.votedFor is None or self.votedFor == candidateId):
                self.votedFor = candidateId
                voteGranted = True
                self.last_heartbeat = time.time()  # reset election timer

            return {"term": self.currentTerm, "voteGranted": voteGranted}

    def on_append_entries(self, term: int, leaderId: str, entries: list, leaderCommit: int) -> dict:
        with self.lock:
            if term < self.currentTerm:
                return {"term": self.currentTerm, "success": False}

            if term > self.currentTerm:
                self.currentTerm = term
                self.votedFor = None

            # accept leader
            if self.state != "Follower":
                self.state = "Follower"
            self.leaderId = leaderId
            self.last_heartbeat = time.time()

            # append new entries (no consistency checks in this lite version)
            if entries:
                for e in entries:
                    self.log.append({"term": e["term"], "cmd": e["cmd"]})
                print(f"[Node {self.id}] Append success")

            # update commit
            if leaderCommit > self.commitIndex:
                self.commitIndex = min(leaderCommit, len(self.log) - 1)
                self._apply_committed()

            return {"term": self.currentTerm, "success": True}

    def on_client_command(self, cmd: str) -> dict:
        with self.lock:
            if self.state != "Leader":
                return {"ok": False, "error": f"Not leader. Leader={self.leaderId}", "term": self.currentTerm}

            entry = {"term": self.currentTerm, "cmd": cmd}
            self.log.append(entry)
            idx = len(self.log) - 1
            print(f"[Leader {self.id}] Append log entry (term={self.currentTerm}, cmd={cmd})")

        # replicate to peers
        acks = 1  # self
        for p in self.peers:
            resp = self._post(p, "/append_entries", {
                "term": self.currentTerm,
                "leaderId": self.id,
                "entries": [entry],
                "leaderCommit": self.commitIndex,
            })
            if resp and resp.get("success"):
                acks += 1

        if acks >= self._majority():
            with self.lock:
                self.commitIndex = idx
                self._apply_committed()
                print(f"[Leader {self.id}] Entry committed (index={idx})")

            # notify followers about commitIndex (heartbeat w/ leaderCommit)
            for p in self.peers:
                self._post(p, "/append_entries", {
                    "term": self.currentTerm,
                    "leaderId": self.id,
                    "entries": [],
                    "leaderCommit": self.commitIndex,
                })
            return {"ok": True, "leader": self.id, "term": self.currentTerm, "commitIndex": self.commitIndex}

        return {"ok": False, "error": "No majority acks", "acks": acks}

    # ---------- loops ----------
    def _election_loop(self):
        while not self.stop_flag:
            time.sleep(0.1)
            with self.lock:
                if self.state == "Leader":
                    continue
                elapsed = time.time() - self.last_heartbeat

            timeout = random.uniform(1.5, 3.0)
            if elapsed < timeout:
                continue

            # start election
            with self.lock:
                self.state = "Candidate"
                self.currentTerm += 1
                term = self.currentTerm
                self.votedFor = self.id
                self.last_heartbeat = time.time()
                print(f"[Node {self.id}] Timeout -> Candidate (term {term})")

            votes = 1
            voters = [self.id]
            for p in self.peers:
                print(f"[Node {self.id}] RequestVote -> {p} (term {term})")
                resp = self._post(p, "/request_vote", {"term": term, "candidateId": self.id})

                if resp and resp.get("term", 0) == term and resp.get("voteGranted"):
                    votes += 1
                    voters.append(p)

            with self.lock:
                if self.currentTerm != term:
                    continue
                if votes >= self._majority():
                    self.state = "Leader"
                    self.leaderId = self.id
                    print(f"[Node {self.id}] Received votes from {', '.join(map(str, voters))} -> Leader (term {term})")
                else:
                    self.state = "Follower"

    def _heartbeat_loop(self):
    while not self.stop_flag:
        time.sleep(0.5)
        with self.lock:
            if self.state != "Leader":
                continue
            term = self.currentTerm
            commit = self.commitIndex

        if time.time() - self._last_hb_log > 2.0:
            print(f"[Leader {self.id}] Heartbeat (term {term})")
            self._last_hb_log = time.time()

        for p in self.peers:
            self._post(p, "/append_entries", {
                "term": term,
                "leaderId": self.id,
                "entries": [],
                "leaderCommit": commit,
            }, timeout=0.8)


# ---------- HTTP server ----------
NODE: Node | None = None

class Handler(BaseHTTPRequestHandler):
    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n).decode("utf-8") if n else "{}"
        return json.loads(raw)

    def _send(self, obj: dict, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        global NODE
        body = self._read_json()

        if self.path == "/request_vote":
            out = NODE.on_request_vote(body["term"], body["candidateId"])
            return self._send(out)

        if self.path == "/append_entries":
            out = NODE.on_append_entries(body["term"], body["leaderId"], body.get("entries", []), body.get("leaderCommit", -1))
            return self._send(out)

        if self.path == "/client_command":
            out = NODE.on_client_command(body["cmd"])
            return self._send(out)

        return self._send({"error": "unknown path"}, 404)

    def log_message(self, format, *args):
        return  # silence default logs

def main():
    global NODE
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--peers", default="")
    args = ap.parse_args()

    peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    NODE = Node(args.id, args.host, args.port, peers)

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[Node {args.id}] Listening on {args.host}:{args.port} peers={peers}")
    srv.serve_forever()

if __name__ == "__main__":
    main()
