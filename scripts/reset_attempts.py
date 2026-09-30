"""Reset the attempt counter of the named WPs (queued or in progress) to a given value, e.g. after
claims were reaped without any agent having worked on them (auth outage), so companies keep their retry.
Usage: reset_attempts.py [--to N] WP-0021-R2 WP-0022-R2 ..."""
import json
import sys
from lib import QUEUE, IN_PROGRESS


def main():
    args = sys.argv[1:]
    to = 1
    if "--to" in args:
        i = args.index("--to")
        to = int(args[i + 1])
        del args[i:i + 2]
    changed = companies = 0
    for wp_id in args:
        for d in (QUEUE, IN_PROGRESS):
            f = d / f"{wp_id}.json"
            if not f.exists():
                continue
            wp = json.loads(f.read_text(encoding="utf-8"))
            if wp.get("attempt") != to:
                wp["attempt"] = to
                f.write_text(json.dumps(wp, indent=2, ensure_ascii=False), encoding="utf-8")
                changed += 1
                companies += len(wp["companies"])
            break
        else:
            print(f"not found in queue/in_progress: {wp_id}")
    print(f"WPs reset to attempt={to}: {changed} | companies: {companies}")


if __name__ == "__main__":
    main()
