#!/usr/bin/env python3
"""Save GitHub's rolling clone history and render honest README badges."""

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import urllib.request


def github_json(repository, endpoint):
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise ValueError("GH_TOKEN needs repository Administration: read for clone traffic")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{endpoint}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "miyoo-game-port-clone-metrics"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def merge_history(previous, traffic, repository, created_at, now):
    today = now.date()
    counts = {}
    for entry in traffic["clones"]:
        day = date.fromisoformat(entry["timestamp"][:10])
        count = entry["count"]
        if type(count) is not int or count < 0 or day > today:
            raise ValueError("Invalid clone traffic entry")
        counts[day.isoformat()] = count
    if sum(counts.values()) != traffic["count"]:
        raise ValueError("Clone entries do not match the API total")
    start = min(counts) if counts else (today - timedelta(days=13)).isoformat()
    end = max(counts) if counts else today.isoformat()
    if previous:
        if previous["repository"] != repository or previous["created_at"] != created_at:
            raise ValueError("History belongs to a different repository")
        complete = previous["complete_history"]
        gaps = list(previous.get("gaps", []))
        if date.fromisoformat(start) > date.fromisoformat(previous["observed_through"]) + timedelta(days=1):
            complete = False
            gaps.append([(date.fromisoformat(previous["observed_through"]) + timedelta(days=1)).isoformat(),
                         (date.fromisoformat(start) - timedelta(days=1)).isoformat()])
        daily = dict(previous["daily_clones"])
        # Replace overlapping days, including zeros/corrections; never add snapshots.
        for key in list(daily):
            if start <= key <= end:
                del daily[key]
        daily.update(counts)
        end = max(end, previous["observed_through"])
        start = min(start, previous["observed_from"])
    else:
        complete = start <= created_at[:10]
        daily = counts
        gaps = []
    return {"schema_version": 1, "repository": repository, "created_at": created_at,
            "updated_at": now.isoformat(), "observed_from": start,
            "observed_through": end, "complete_history": complete,
            "gaps": gaps, "daily_clones": dict(sorted(daily.items()))}


def figures(history, today):
    monday = (today - timedelta(days=today.weekday())).isoformat()
    week = sum(value for day, value in history["daily_clones"].items()
               if monday <= day <= today.isoformat())
    week_complete = history["observed_from"] <= max(monday, history["created_at"][:10])
    week_complete = week_complete and history["observed_through"] >= max(monday, history["created_at"][:10])
    week_complete = week_complete and not any(start <= today.isoformat() and end >= monday
                                              for start, end in history.get("gaps", []))
    return week, sum(history["daily_clones"].values()), week_complete


def badge(label, value, updated_at):
    left = 12 + len(label) * 7
    right = max(36, 14 + len(value) * 7)
    width = left + right
    title = escape(f"{label}: {value}. Snapshot: {updated_at}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{title}">
  <title>{title}</title>
  <rect width="{width}" height="20" rx="3" fill="#555"/>
  <path d="M{left} 0h{right}v20H{left}z" fill="#007ec6"/>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
    <text x="{left / 2}" y="14">{escape(label)}</text>
    <text x="{left + right / 2}" y="14">{escape(value)}</text>
  </g>
</svg>
'''


def write_metrics(output, history, today):
    week, overall, week_complete = figures(history, today)
    snapshot = f'{history["updated_at"]}; traffic through {history["observed_through"]} UTC'
    files = {
        "history.json": json.dumps(history, indent=2) + "\n",
        "clones-week.svg": badge("Clones this week", f"{week:,}" if week_complete else "partial", snapshot),
        "clones-overall.svg": badge("Clones overall" if history["complete_history"] else "Clones tracked",
                                    f"{overall:,}", snapshot),
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        temporary = output / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "devarshi16/miyoo-game-port"))
    parser.add_argument("--output", type=Path, default=Path(".github/metrics"))
    parser.add_argument("--traffic-json", type=Path, help="Use a saved API response (offline bootstrap/testing)")
    parser.add_argument("--repository-json", type=Path, help="Use saved repository metadata")
    args = parser.parse_args()
    # Fetch and validate everything before replacing any public metrics.
    repo = json.loads(args.repository_json.read_text()) if args.repository_json else github_json(args.repository, "")
    traffic = json.loads(args.traffic_json.read_text()) if args.traffic_json else github_json(args.repository, "/traffic/clones?per=day")
    path = args.output / "history.json"
    previous = json.loads(path.read_text()) if path.exists() else None
    now = datetime.now(timezone.utc)
    history = merge_history(previous, traffic, args.repository, repo["created_at"], now)
    write_metrics(args.output, history, now.date())


if __name__ == "__main__":
    main()
