#!/usr/bin/env python3
"""
Signal 3: GitHub Frontend Activity Scanner
Checks company GitHub orgs for frontend repository activity.
"""

import csv
import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_CSV = os.environ.get("SEED_CSV", os.path.join(REPO, "data", "seed.csv"))
OUTPUT_JSON = os.environ.get("OUTPUT_JSON", os.path.join(REPO, "results", "signal-github.json"))
SCAN_DATE = os.environ.get("SCAN_DATE") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Frontend detection criteria
FRONTEND_LANGUAGES = {"javascript", "typescript", "css", "html", "vue", "scss", "sass", "less", "svelte"}
FRONTEND_KEYWORDS = {"react", "vue", "nextjs", "next.js", "frontend", "front-end", "design-system",
                      "storybook", "ui", "components", "webapp", "web-app", "dashboard", "portal"}
FRONTEND_NAME_PATTERNS = ["-ui", "-web", "-frontend", "-app", "design-system", "storybook",
                           "components", "-dashboard", "-portal", "web-client"]

HEADERS = {
    "User-Agent": "gtm-signal-scanner/1.0",
    "Accept": "application/vnd.github.v3+json"
}

rate_limit_remaining = 60
rate_limit_hit = False
api_calls_made = 0


def github_get(url, retries=1):
    """Make a GitHub API GET request with rate limit awareness."""
    global rate_limit_remaining, rate_limit_hit, api_calls_made

    if rate_limit_hit:
        return None

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        time.sleep(1.5)  # Be gentle with rate limits
        api_calls_made += 1
        with urllib.request.urlopen(req, timeout=15) as resp:
            rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 60))
            if rate_limit_remaining < 3:
                print(f"  [WARN] Rate limit nearly exhausted: {rate_limit_remaining} remaining")
                rate_limit_hit = True
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"  [RATE LIMIT] 403 on {url}")
            rate_limit_hit = True
            return None
        elif e.code == 404:
            return None
        elif e.code == 409:
            # Empty repo / no commits
            return None
        else:
            print(f"  [HTTP {e.code}] {url}")
            if retries > 0:
                time.sleep(3)
                return github_get(url, retries - 1)
            return None
    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        if retries > 0:
            time.sleep(3)
            return github_get(url, retries - 1)
        return None


def is_frontend_repo(repo):
    """Determine if a repo is frontend-related based on language, topics, name, and description."""
    score = 0
    reasons = []

    # Check language
    lang = (repo.get("language") or "").lower()
    if lang in FRONTEND_LANGUAGES:
        score += 2
        reasons.append(f"lang:{lang}")

    # Check topics
    topics = [t.lower() for t in (repo.get("topics") or [])]
    frontend_topics = set(topics) & FRONTEND_KEYWORDS
    if frontend_topics:
        score += 3
        reasons.append(f"topics:{','.join(frontend_topics)}")

    # Check repo name
    name = repo.get("name", "").lower()
    for pattern in FRONTEND_NAME_PATTERNS:
        if pattern in name:
            score += 2
            reasons.append(f"name:{pattern}")
            break

    # Check description
    desc = (repo.get("description") or "").lower()
    for kw in FRONTEND_KEYWORDS:
        if kw in desc:
            score += 1
            reasons.append(f"desc:{kw}")
            break

    return score >= 2, score, reasons


def get_participation_stats(org, repo_name):
    """Get weekly commit participation stats for a repo."""
    url = f"https://api.github.com/repos/{org}/{repo_name}/stats/participation"
    data = github_get(url)
    if not data or not isinstance(data, dict):
        return None
    return data.get("all", [])


def get_latest_commit_date(org, repo_name):
    """Get the date of the most recent commit."""
    url = f"https://api.github.com/repos/{org}/{repo_name}/commits?per_page=1"
    data = github_get(url)
    if data and isinstance(data, list) and len(data) > 0:
        commit_data = data[0].get("commit", {}).get("committer", {})
        return commit_data.get("date", "")
    return ""


def analyze_org(company_name, github_org):
    """Analyze a GitHub org for frontend activity."""
    global rate_limit_hit

    if rate_limit_hit:
        return {
            "found": False,
            "frontend_repos": 0,
            "recent_commits": 0,
            "details": "Skipped due to GitHub API rate limit"
        }

    print(f"\n[{api_calls_made}] Scanning {company_name} -> github.com/{github_org}")

    # List repos
    repos_url = f"https://api.github.com/orgs/{github_org}/repos?per_page=100&sort=updated"
    repos = github_get(repos_url)

    if repos is None:
        # Try as user instead of org
        repos_url = f"https://api.github.com/users/{github_org}/repos?per_page=100&sort=updated"
        repos = github_get(repos_url)

    if repos is None or not isinstance(repos, list):
        return {
            "found": False,
            "frontend_repos": 0,
            "recent_commits": 0,
            "details": f"GitHub org '{github_org}' not accessible or rate limited"
        }

    if len(repos) == 0:
        return {
            "found": True,
            "frontend_repos": 0,
            "recent_commits": 0,
            "details": f"Org '{github_org}' exists but has no public repos"
        }

    # Find frontend repos
    frontend_repos = []
    for repo in repos:
        if repo.get("fork") or repo.get("archived"):
            continue
        is_fe, score, reasons = is_frontend_repo(repo)
        if is_fe:
            frontend_repos.append({
                "name": repo["name"],
                "score": score,
                "reasons": reasons,
                "language": repo.get("language", ""),
                "updated_at": repo.get("updated_at", ""),
                "stars": repo.get("stargazers_count", 0)
            })

    # Sort by score then stars
    frontend_repos.sort(key=lambda r: (r["score"], r["stars"]), reverse=True)

    if not frontend_repos:
        # Check if any repos have JS/TS even if not strongly frontend
        js_repos = [r for r in repos if (r.get("language") or "").lower() in ("javascript", "typescript") and not r.get("fork")]
        if js_repos:
            return {
                "found": True,
                "frontend_repos": 0,
                "recent_commits": 0,
                "details": f"Org has {len(repos)} public repos, {len(js_repos)} JS/TS repos but none strongly frontend-signaled"
            }
        return {
            "found": True,
            "frontend_repos": 0,
            "recent_commits": 0,
            "details": f"Org has {len(repos)} public repos but none appear frontend-related"
        }

    # Analyze top frontend repos (limit to top 5 to save API calls)
    top_repos = frontend_repos[:5]
    total_recent_commits = 0
    total_prior_commits = 0
    repo_details = []

    for fr in top_repos:
        if rate_limit_hit:
            break

        repo_name = fr["name"]

        # Get participation stats (52 weeks of commit data)
        weeks = get_participation_stats(github_org, repo_name)

        recent_4w = 0
        prior_4w = 0
        if weeks and len(weeks) >= 8:
            recent_4w = sum(weeks[-4:])
            prior_4w = sum(weeks[-8:-4])
        elif weeks and len(weeks) >= 4:
            recent_4w = sum(weeks[-4:])

        total_recent_commits += recent_4w
        total_prior_commits += prior_4w

        # Detect spike
        spike = ""
        if prior_4w > 0 and recent_4w > prior_4w * 1.5:
            spike = f" [SPIKE +{int((recent_4w/prior_4w - 1)*100)}%]"
        elif prior_4w == 0 and recent_4w > 0:
            spike = " [NEW ACTIVITY]"

        repo_details.append(f"{repo_name}({fr['language']},{'|'.join(fr['reasons'])},{recent_4w}c/4w{spike})")

    # Build summary
    spike_status = ""
    if total_prior_commits > 0 and total_recent_commits > total_prior_commits * 1.5:
        pct = int((total_recent_commits / total_prior_commits - 1) * 100)
        spike_status = f" ACTIVITY SPIKE: +{pct}% vs prior 4 weeks."
    elif total_prior_commits > 0 and total_recent_commits < total_prior_commits * 0.5:
        spike_status = " Activity declining vs prior 4 weeks."

    details = (
        f"{len(frontend_repos)} frontend repos found (of {len(repos)} total). "
        f"Top repos: {'; '.join(repo_details)}. "
        f"Last 4w: {total_recent_commits} commits, prior 4w: {total_prior_commits}.{spike_status}"
    )

    return {
        "found": True,
        "frontend_repos": len(frontend_repos),
        "recent_commits": total_recent_commits,
        "prior_4w_commits": total_prior_commits,
        "details": details
    }


def main():
    global rate_limit_hit

    # Read seed CSV
    companies = []
    with open(SEED_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("company_name", "").strip()
            if name:
                companies.append({
                    "name": name,
                    "github_org": row.get("github_org", "").strip(),
                    "has_ats": bool(row.get("ats_url", "").strip())
                })

    print(f"Loaded {len(companies)} companies, {sum(1 for c in companies if c['github_org'])} have GitHub orgs")

    # Prioritize: companies with ATS first (more likely to stack signals)
    companies_with_ats = [c for c in companies if c["has_ats"] and c["github_org"]]
    companies_no_ats = [c for c in companies if not c["has_ats"] and c["github_org"]]
    companies_no_gh = [c for c in companies if not c["github_org"]]

    ordered = companies_with_ats + companies_no_ats

    print(f"Priority order: {len(companies_with_ats)} with ATS+GH, {len(companies_no_ats)} GH only, {len(companies_no_gh)} no GH")

    results = {}

    # Companies with GitHub orgs
    for company in ordered:
        result = analyze_org(company["name"], company["github_org"])
        results[company["name"]] = result
        print(f"  -> {company['name']}: {result['frontend_repos']} FE repos, {result['recent_commits']} recent commits")

        if rate_limit_hit:
            print("\n[!] Rate limit hit. Remaining orgs will be marked as skipped.")
            break

    # Mark remaining orgs as skipped if rate limited
    if rate_limit_hit:
        for company in ordered:
            if company["name"] not in results:
                results[company["name"]] = {
                    "found": False,
                    "frontend_repos": 0,
                    "recent_commits": 0,
                    "details": "Skipped due to GitHub API rate limit"
                }

    # Companies without GitHub orgs
    for company in companies_no_gh:
        results[company["name"]] = {
            "found": False,
            "frontend_repos": 0,
            "recent_commits": 0,
            "details": "No GitHub org discovered"
        }

    # Build output
    output = {
        "signal": "github_activity",
        "scan_date": SCAN_DATE,
        "api_calls_made": api_calls_made,
        "rate_limited": rate_limit_hit,
        "companies_scanned": sum(1 for r in results.values() if r.get("found")),
        "results": results
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone. Results written to {OUTPUT_JSON}")
    print(f"API calls made: {api_calls_made}")
    print(f"Rate limited: {rate_limit_hit}")
    print(f"Companies with frontend repos: {sum(1 for r in results.values() if r.get('frontend_repos', 0) > 0)}")
    print(f"Total companies in results: {len(results)}")


if __name__ == "__main__":
    main()
