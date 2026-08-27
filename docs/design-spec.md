# GTM Signal Scanner — Design Spec

## Context

This is the design spec for a lightweight, homegrown signal identification system. The goal is to surface companies that match an ICP and show buying signals, so a founder can decide who gets outreach.

This is a learning tool first. At 30-40 companies, the value isn't time savings — it's discovering which signals actually predict good conversations. The feedback loop is the core feature. If signals prove predictive after 4-6 runs, the system scales up. If not, you stop early with minimal investment.

**Cost target: $0.** Everything runs through an AI coding agent on a flat-rate plan. Free APIs only.

**ICP:** Product managers and UX/product designers at mid-market B2B SaaS companies. 50-1,000 employees. Web-based products. US, Canada, UK, Western Europe. Exclude healthcare, finance, agencies, regulated industries.

---

## Architecture

**Claude Code IS the scanner.** No persistent scripts, no external servers. Claude Code reads a seed CSV, checks signal sources, reasons about what it finds, and writes results. The "source code" is scanning instructions in `CLAUDE.md`.

### File Structure

```
signals/
├── CLAUDE.md                       # Scanning instructions Claude Code follows
├── data/
│   ├── seed.csv                    # Company seed list (user maintains)
│   └── feedback.csv                # Accumulated ratings across all runs
├── results/
│   ├── latest.csv                  # Most recent scan (user's working file)
│   └── archive/
│       └── YYYY-MM-DD-scan.json    # Full structured data per run
```

### Run Flow

1. User says "run a scan"
2. Claude Code reads `data/seed.csv` and `data/feedback.csv`
3. For each company: checks job postings, Storybook, GitHub activity, team page
4. Scores and stacks signals into tiers
5. Writes `results/archive/YYYY-MM-DD-scan.json` (full archive) and `results/latest.csv` (working file)
6. Reports summary: "Scanned 35 companies. 4 hot, 8 warm, 23 no signal."

### Feedback Flow

1. User opens `results/latest.csv` in a spreadsheet
2. Marks each surfaced company as `good` / `bad` / `skip` in the feedback column, optionally adds notes
3. Saves the file
4. Tells Claude Code "process my feedback"
5. Claude Code reads `results/latest.csv`, appends rated rows to `data/feedback.csv` (never overwrites)
6. Next scan, Claude Code reads feedback history and adjusts weighting/reporting

### Learning Loop

After 4-6 runs, user asks Claude Code to analyze feedback data. Claude Code runs regression across archived scans and feedback, reports which signals predict good conversations, and recommends instruction adjustments.

---

## Data Model

### Seed CSV (`data/seed.csv`)

User provides initially:
```
company_name, url, country, employee_count
```

Claude Code enriches on first run:
```
company_name, url, country, employee_count, ats_type, ats_url, github_org, team_page_url
```

Discovered fields persist. Claude Code only re-discovers if they stop working.

### Scan Archive (`results/archive/YYYY-MM-DD-scan.json`)

```json
{
  "scan_date": "2026-04-02",
  "companies": [{
    "name": "Acme Corp",
    "url": "acme.com",
    "signals": {
      "job_postings": {
        "found": true,
        "roles": ["Senior PM", "Product Designer"],
        "velocity_language": true,
        "reasoning": "Description mentions 'rapid prototyping' and 'ship without waiting for eng cycles'"
      },
      "storybook": {
        "found": true,
        "url": "storybook.acme.com"
      },
      "github_activity": {
        "found": true,
        "frontend_repos": 3,
        "recent_commits": 47,
        "details": "Spike in design-system repo commits over last 30 days"
      },
      "team_changes": {
        "found": false
      }
    },
    "signal_count": 3,
    "strength": "hot"
  }]
}
```

The `reasoning` field captures why Claude Code flagged something — enables quality judgment, not just presence/absence.

### Latest CSV (`results/latest.csv`)

```
company_name, strength, signal_count, job_postings, storybook, github, team_changes, top_signal_detail, feedback, notes
```

User fills in `feedback` (good/bad/skip) and `notes`. All other columns written by Claude Code.

### Feedback CSV (`data/feedback.csv`)

```
company_name, scan_date, strength, feedback, notes
```

Append-only. Grows across all runs. Source of truth for regression analysis.

---

## Signals (v1)

### Signal 1: Job Postings (semantic analysis) — Primary

- **Discovery:** Claude Code visits each company's careers page, detects ATS (Greenhouse, Lever, Ashby) by URL patterns. Saves ATS type and URL to seed CSV.
- **Scanning:** Hits public ATS APIs (free, no auth):
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
  - Lever: `https://api.lever.co/v0/postings/{slug}`
  - Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}`
- **Filtering:** PM, product design, Head of Product, VP Product roles
- **Analysis:** Claude Code reads full job descriptions, flags velocity/prototyping/design system language. Captures reasoning.
- **Key insight:** The signal isn't "they're hiring a PM" — it's what the description says about how the company works. This semantic analysis is Claude Code's core advantage over keyword matching.

### Signal 2: Storybook / Design System Presence

- Checks: `storybook.{domain}`, `design.{domain}`, `ds.{domain}`, `{domain}/storybook`
- Checks main site source for Storybook-specific meta tags or script references
- Binary signal (found/not found) but strong for stacking — a public Storybook means structured design workflow, which is where the product fits in
- Cached: if found once, don't re-check every run (just verify URL still resolves)

### Signal 3: GitHub Front-End Activity

- **Discovery:** Claude Code finds the company's GitHub org (search GitHub orgs, check company site footer)
- **Scanning:** GitHub public API (5000 req/hr with free personal token):
  - List repos, filter by frontend indicators (React, Vue, Next.js, CSS, Storybook in topics/languages)
  - Check recent commit activity on frontend repos
  - Compare last 30 days vs prior 30 days for spike detection
- **Stacking signal** — ambiguous alone, strengthens the case when combined with other signals

### Signal 4: Team Page Diffing (people-level) — Lower Priority

- **First run:** Claude Code visits each company's team/about page, snapshots product/design leadership names
- **Subsequent runs:** Fetches page, diffs against previous snapshot. Flags new PM/design leadership.
- **Supplemented by:** Web search for `"{company name}" "Head of Product" OR "VP Product" OR "Head of Design"` filtered to last 30 days
- **Graceful degradation:** If team page isn't parseable, Claude Code notes "team page not usable" in seed CSV and skips on future runs

### Rate Limit Budget (40 companies, weekly)

| Source | Calls/company | Total (40) | Limit |
|--------|--------------|------------|-------|
| ATS APIs | 1 | 40 | Unlimited (public) |
| Storybook check | 3-4 URL checks | ~150 | Simple HTTP |
| GitHub API | 3-5 | ~200 | 5000/hr (free token) |
| Team page + web search | 2 | ~80 | Firecrawl free (500/mo) |

Well within free tier limits for weekly runs.

---

## Signal Stacking & Scoring

### Tiers (not numeric scores)

| Tier | Rule | Meaning |
|------|------|---------|
| **Hot** | 3+ signals, OR job posting with velocity language + Storybook | Strong product fit, multiple indicators |
| **Warm** | 2 signals in any combination | Worth watching, may be outreach-ready |
| **Monitoring** | 1 signal | On the radar, not actionable yet |

### Special Combo Rules

- Job posting with velocity language + Storybook = **hot** (strongest product-specific combo, promoted even with only 2 signals)
- New PM/design hire + any other signal = bump up one tier (new decision-maker = window of openness)

### Why Tiers Not Scores

At 30-40 companies with 4 signals, numeric scores create false precision. You need to know the bucket, not a decimal. Tiers keep it honest.

### Feedback-Driven Evolution

After several runs, Claude Code reports patterns: "Companies you rated 'good' had Storybook 80% of the time. 'Bad' ratings were mostly job-posting-only." User decides whether to adjust tier rules and updates `CLAUDE.md` accordingly.

### Output Sorting

`latest.csv` sorted by tier (hot first, then warm, then monitoring), then by signal count descending within each tier. User scans top-down and stops when they've seen enough.

---

## What's Explicitly NOT in v1

- No website or dashboard (CSV is the interface)
- No outreach automation or email generation
- No funding signal (commodity data, dropped)
- No changelog signal (ambiguous, dropped)
- No tech stack detection (not differentiating enough)
- No scheduled/automated runs (manual trigger only)
- No persistent scripts (Claude Code runs live)

---

## What v1 Success Looks Like

The operator points this at 30-40 target companies, runs it weekly for 4-6 weeks, and gets back a ranked CSV of who showed signals and what they showed. They rate the results, and after 4-6 cycles has enough data to answer: "Are these signals actually predicting good conversations?" If yes, scale to 100+ companies and consider a dashboard (v2). If no, adjust signals or stop — minimal sunk cost either way.

---

## Implementation Plan

### Step 1: Project Setup
- Initialize git repo
- Create directory structure (`data/`, `results/`, `results/archive/`)
- Write `CLAUDE.md` with full scanning instructions
- Create `data/seed.csv` template with headers
- Create empty `data/feedback.csv` with headers
- Add your planning-tool directory and `.gitignore`

### Step 2: Seed List Bootstrap
- the operator provides his initial 30-40 companies as CSV (name, url, country, employee_count)
- Claude Code runs ATS discovery: visits each company's careers page, detects Greenhouse/Lever/Ashby, saves to seed CSV
- Claude Code discovers GitHub orgs where possible
- Claude Code checks for team/about pages and records URLs
- Result: enriched seed CSV ready for scanning

### Step 3: First Scan
- Run all 4 signals against the enriched seed list
- Write first `results/archive/YYYY-MM-DD-scan.json`
- Write first `results/latest.csv`
- Review results together — sanity check signal quality before entering the feedback loop

### Step 4: Feedback Loop
- the operator reviews and rates `latest.csv`
- Claude Code processes feedback into `data/feedback.csv`
- Run second scan incorporating feedback context
- Iterate weekly

### Verification
- After Step 1: confirm file structure exists and `CLAUDE.md` is complete
- After Step 2: confirm enriched seed CSV has ATS URLs for the majority of companies
- After Step 3: confirm scan JSON and CSV are well-formed, signals are populated, tiers are assigned correctly
- After Step 4: confirm feedback CSV appends correctly and next scan references prior feedback
