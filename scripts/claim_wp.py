"""Atomically claim the next queued workpackage (queue -> in_progress) and stamp its deadline.
Prints the claimed path. Exit 1 = queue empty, exit 2 = concurrency cap reached."""
import json
import os
import sys
from datetime import timedelta
from lib import QUEUE, IN_PROGRESS, load_config, now_utc, iso


def main():
    cfg = load_config()
    if len(list(IN_PROGRESS.glob("WP-*.json"))) >= cfg["max_concurrent_agents"]:
        print("concurrency cap reached", file=sys.stderr)
        sys.exit(2)
    for wp in sorted(QUEUE.glob("WP-*.json")):
        dest = IN_PROGRESS / wp.name
        try:
            os.rename(wp, dest)        # atomic on one filesystem: two claimers can't both win
        except FileNotFoundError:
            continue
        data = json.loads(dest.read_text())
        t = now_utc()
        data["claimed_utc"] = iso(t)
        data["deadline_utc"] = iso(t + timedelta(minutes=data["limits"]["minutes_per_workpackage"]))
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(dest)
        return
    sys.exit(1)


if __name__ == "__main__":
    main()
