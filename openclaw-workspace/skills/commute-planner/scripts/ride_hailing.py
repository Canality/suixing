#!/usr/bin/env python3
"""打车/单车预估 — 调用Mock API预估出行费用和时间。

Usage:
  python ride_hailing.py --origin "望京SOHO" --destination "798" --mode 打车
  python ride_hailing.py --origin "望京SOHO" --destination "颐堤港" --mode 美团单车
"""

import json
import argparse
import urllib.request
import os

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")


def estimate(origin: str, destination: str, mode: str = "打车") -> dict:
    body = json.dumps({"origin": origin, "destination": destination, "mode": mode}).encode("utf-8")
    req = urllib.request.Request(
        f"{MOCK_API}/api/ride/estimate",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            data["source_label"] = "[高德]"
            return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="出行预估")
    parser.add_argument("--origin", required=True, help="出发地")
    parser.add_argument("--destination", required=True, help="目的地")
    parser.add_argument("--mode", default="打车", choices=["打车", "美团单车", "地铁"])
    args = parser.parse_args()

    result = estimate(args.origin, args.destination, args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
