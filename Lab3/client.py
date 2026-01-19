import argparse, json
from urllib.request import Request, urlopen

def post(url, data):
    req = Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=2.0) as resp:
        return resp.read().decode("utf-8")

ap = argparse.ArgumentParser()
ap.add_argument("--leader", required=True)   # ip:port
ap.add_argument("--cmd", required=True)      # "SET x=5"
args = ap.parse_args()

print(post(f"http://{args.leader}/client_command", {"cmd": args.cmd}))
