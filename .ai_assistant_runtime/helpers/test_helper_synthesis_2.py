import json
import sys

def run(payload):
    return {
        "helper": "test_helper_synthesis_2",
        "purpose": "echo the payload back",
        "payload": payload
    }

if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {}
    result = run(payload)
    print(json.dumps(result, indent=2, ensure_ascii=True))
