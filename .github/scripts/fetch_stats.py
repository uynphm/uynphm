"""Fetch last-year contribution total and activity counts, private repos included.

Usage: STATS_TOKEN=... python3 fetch_stats.py <login> out.json
The token must be able to read the private repos you want counted (e.g. your work org).
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://api.github.com"
TOKEN = os.environ["STATS_TOKEN"]


def get(path: str, params: dict | None = None) -> dict:
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def graphql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(f"{API}/graphql", data=body, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]


def count(kind: str, q: str) -> int:
    return get(f"/search/{kind}", {"q": q, "per_page": 1})["total_count"]


CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { firstDay contributionDays { contributionCount } }
      }
    }
  }
}"""


def calendar(login: str, since: str, until: str) -> dict:
    """Total contributions in the window, days with any contribution, and a per-week series for the chart."""
    res = graphql(CALENDAR_QUERY, {"login": login, "from": f"{since}T00:00:00Z", "to": f"{until}T23:59:59Z"})
    cal = res["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [{"start": w["firstDay"], "count": sum(d["contributionCount"] for d in w["contributionDays"])} for w in cal["weeks"]]
    active = sum(1 for w in cal["weeks"] for d in w["contributionDays"] if d["contributionCount"])
    return {"total": cal["totalContributions"], "active_days": active, "weeks": weeks}


PR_COMMITS_QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 100, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest { commits { totalCount } } }
  }
}"""


def pr_commits(login: str, since: str) -> int:
    """Commits inside your PRs. Squash merges land each PR on main as one commit,
    so the default-branch commit count alone undercounts. Search caps at 1,000 PRs."""
    total, after = 0, None
    for _ in range(10):
        res = graphql(PR_COMMITS_QUERY, {"q": f"author:{login} type:pr created:>={since}", "after": after})["search"]
        total += sum(pr["commits"]["totalCount"] for pr in res["nodes"] if pr)
        if not res["pageInfo"]["hasNextPage"]:
            break
        after = res["pageInfo"]["endCursor"]
    return total


def main() -> None:
    login, out = sys.argv[1], sys.argv[2]
    since = (date.today() - timedelta(days=365)).isoformat()
    until = date.today().isoformat()
    stats = {
        "since": since,
        "until": until,
        **calendar(login, since, until),
        "commits": max(count("commits", f"author:{login} author-date:>={since}"), pr_commits(login, since)),
        "prs": count("issues", f"author:{login} type:pr created:>={since}"),
        "reviews": count("issues", f"reviewed-by:{login} -author:{login} type:pr created:>={since}"),
        "issues": count("issues", f"author:{login} type:issue created:>={since}"),
    }
    with open(out, "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
