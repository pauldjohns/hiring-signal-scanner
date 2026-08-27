# GTM Signal Scanner

## What This Is

A signal identification system you run with Claude Code. It scans a list of target companies for buying signals, scores and stacks them into tiers, and outputs a ranked CSV for manual review and outreach decisions.

The four signals below are tuned for a product sold to product managers and designers. Change the role list, the language patterns and the ICP block to match what you sell - that is the intended way to use this file.

## ICP — CONFIGURE THIS FIRST

Define your own. Everything below scores against it, so a scanner running someone else's ICP is
just a random-company generator. Be specific, and be specific about the exclusions - who you refuse
is what stops the list drifting to whoever is easiest to find.

- **Roles:** the titles you sell to
- **Companies:** segment, size band, product shape
- **Geography:** where you can actually sell
- **Exclude:** sectors and company types you will not pursue, and why

## Commands

### "run a scan"

1. Read `data/seed.csv` for the company list
2. Read `data/feedback.csv` for past ratings (if any exist)
3. For each company, run all 4 signal checks (see Signal Detection below)
4. Score and stack signals into tiers (see Scoring below)
5. Write results to `results/archive/YYYY-MM-DD-scan.json` (full structured data)
6. Write results to `results/latest.csv` (user's working file, sorted by tier)
7. Report summary: how many companies scanned, how many hot/warm/monitoring

### "process my feedback"

1. Read `results/latest.csv`
2. Find rows where the `feedback` column is filled in (good/bad/skip)
3. Append those rows to `data/feedback.csv` (NEVER overwrite — always append)
4. Report how many ratings were added and running total

### "analyze my feedback"

1. Read `data/feedback.csv` and all archived scans in `results/archive/`
2. Correlate: which signals appear most often in "good" vs "bad" rated companies?
3. Report patterns and recommend adjustments to signal weights or tier rules

## Signal Detection

### Signal 1: Job Postings (semantic analysis)

**Discovery (first run or when ats_url is empty):**
- Visit the company's URL + `/careers`, `/jobs`, `/careers/open-positions`, and similar common patterns
- Look for links to `boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`
- Save the ATS type and URL back to `data/seed.csv`

**Scanning:**
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- Lever: `https://api.lever.co/v0/postings/{slug}`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}`
- Filter for the role titles in your ICP (list them here)
- For each matching role, read the full job description

**Semantic analysis — what to flag:**
- CONFIGURE: list the language that signals your buyer has your problem. Four or five categories,
  each with the exact phrases you have seen in real job descriptions. The examples that shipped with
  this file were one company's and have been removed - yours will be different and more useful.

**Output:**
- `found`: boolean
- `roles`: list of matching role titles
- `velocity_language`: boolean (did any description contain the language above?)
- `reasoning`: 1-2 sentences explaining WHY this was flagged, quoting specific language from the description

### Signal 2: Storybook / Design System Presence

**Check these URLs (replace {domain} with the company's domain):**
- `https://storybook.{domain}`
- `https://design.{domain}`
- `https://ds.{domain}`
- `https://{domain}/storybook`
- `https://{domain}/design-system`

**Also check:**
- Fetch the company's main page source and look for references to `storybook`, `@storybook`, or design system meta tags

**Caching:**
- If Storybook was found on a previous run, just verify the URL still resolves. Don't re-scan all patterns.
- If found, record the URL in the scan results.

**Output:**
- `found`: boolean
- `url`: the Storybook/design system URL if found

### Signal 3: GitHub Front-End Activity

**Discovery (first run or when github_org is empty):**
- Search GitHub orgs for the company name
- Check the company's website footer for GitHub links
- Save the org name to `data/seed.csv`

**Scanning (requires GitHub personal access token for higher rate limits):**
- List the org's public repos
- Filter for frontend indicators: repos with React, Vue, Next.js, TypeScript, CSS, Storybook in topics, languages, or repo descriptions
- For frontend repos, check commit activity over the last 30 days vs prior 30 days
- Flag if there's a significant spike (>50% increase) in frontend commit activity

**Output:**
- `found`: boolean (true if there's meaningful frontend activity)
- `frontend_repos`: count of frontend repos
- `recent_commits`: commit count in last 30 days across frontend repos
- `details`: description of what was found (e.g., "Spike in design-system repo")

### Signal 4: Team Page Diffing (people-level)

**Discovery (first run):**
- Visit the company's URL + `/about`, `/team`, `/about/team`, `/company`, `/about-us`
- Find the page that lists team members, especially product/design leadership
- Save the working URL to `data/seed.csv` as `team_page_url`
- Snapshot the names and roles found under product/design

**Subsequent runs:**
- Fetch the team page again
- Compare against previous snapshot (stored in the prior scan archive)
- Flag new names in product/design leadership positions

**Supplementary search:**
- Web search for: `"{company_name}" "Head of Product" OR "VP Product" OR "VP Design" OR "Head of Design"` filtered to last 30 days
- Flag if recent hire announcements are found

**Graceful degradation:**
- If the team page doesn't have parseable team data, note "team page not usable" in seed CSV and skip on future runs

**Output:**
- `found`: boolean (true if new product/design leadership detected)
- `new_hires`: list of new names and roles
- `source`: "team_page" or "web_search"

## Scoring & Stacking

### Tiers

| Tier | Rule |
|------|------|
| **Hot** | 3+ signals, OR (job posting with velocity language + Storybook present) |
| **Warm** | 2 signals in any combination |
| **Monitoring** | 1 signal |
| **No signal** | 0 signals (don't include in latest.csv) |

### Special Combo Rules

- Job posting with velocity language + Storybook = **hot** (even with only 2 signals)
- New PM/design hire + any other signal = bump up one tier

### Feedback-Driven Adjustments

When feedback data exists, note patterns before scanning:
- If a signal combo has been rated "good" multiple times, mention it in the summary
- If a signal combo has been rated "bad" multiple times, flag it as potentially unreliable
- Do NOT automatically change tier rules — recommend changes and let the user decide

## Output Formats

### latest.csv columns

```
company_name,strength,signal_count,job_postings,storybook,github,team_changes,top_signal_detail,feedback,notes
```

- `strength`: hot / warm / monitoring
- `job_postings`, `storybook`, `github`, `team_changes`: yes / no
- `top_signal_detail`: the most interesting finding in 1 sentence
- `feedback` and `notes`: left blank for user to fill in
- Sorted: hot first, then warm, then monitoring. Within each tier, by signal_count descending.

### archive JSON

Full structured data as described in Signal Detection outputs above. One file per scan run, named `YYYY-MM-DD-scan.json`.

## Important Notes

- **Cost: $0.** Only use free APIs and public endpoints. No paid services.
- **No outreach automation.** This system identifies targets. You decide who to contact.
- **Reasoning matters.** Always capture WHY a signal was flagged, not just that it was found.
- **Be honest about confidence.** If a signal is weak or ambiguous, say so in the reasoning field.
- **Preserve the seed CSV.** When enriching, add columns — never delete existing data.
