# hiring-signal-scanner

Watches a list of target companies for four signals that a founder can act on, scores them into
tiers, and writes a ranked CSV. The scanner is Claude Code itself: `CLAUDE.md` holds the scanning
instructions, so there is no server, no scheduler, and no paid API. One Python script does the
GitHub-heavy part where scripted rate-limit handling beats an agent doing it by hand.

Built for a small team doing outbound by hand and wanting a better reason to pick this company
over that one.

## The four signals

1. **Job postings.** Find the company’s ATS (Greenhouse, Lever, Ashby all have free JSON endpoints),
   pull the roles you care about, and read the descriptions – not for keywords, for *language*:
   shipping velocity, design systems, reducing engineering dependency, handoff pain. A job
   description is a company writing down its problem in public.
2. **Design system presence.** Probe the handful of conventional subdomains and paths where a
   Storybook lives, plus the homepage source.
3. **GitHub front-end activity.** Find the org, filter repos to front-end by language, topic and
   name pattern, and compare commit volume in the last 30 days against the 30 before it. A spike in
   a design-system repo is a different signal from steady maintenance.
4. **Team-page diffing.** Snapshot product and design leadership, then compare on the next run. A new
   Head of Product in the last month is the single best time to show up.

Then stack them. Three signals is hot; two is warm; one is monitoring. Two combinations promote:
velocity language plus a live Storybook goes straight to hot, and a new product or design hire bumps
whatever else you found up one tier.

## The part that matters

The feedback loop, not the scanning. `data/feedback.csv` accumulates a good/bad/skip rating per
company across runs, and “analyze my feedback” correlates which signal combinations actually preceded
good conversations. At 30–40 companies this saves you no time at all – its whole value is telling you
within a few runs whether your signals predict anything. If they don’t, you have learned that
cheaply, which was the point.

Do not let the system auto-tune its own tier rules. It recommends; you decide. A scoring model that
silently drifts toward whatever you clicked last week is how you end up with a list that flatters you.

## Use it

```bash
cp examples/seed.example.csv data/seed.csv     # your target companies
```

Then open the repo in Claude Code and say “run a scan”. `CLAUDE.md` is the program: it defines the
signal checks, the tiers, the output format, and the two other commands (“process my feedback”,
“analyze my feedback”).

For the GitHub signal at volume:

```bash
GITHUB_TOKEN=ghp_… python3 scripts/signal3_github.py
```

Unauthenticated GitHub gives you 60 calls an hour, which is not enough for 40 orgs. With a read-only
token it is 5,000. The script also accepts `SEED_CSV`, `OUTPUT_JSON` and `SCAN_DATE` as environment
variables and otherwise resolves paths relative to the repo.

**Retune `CLAUDE.md` before your first run.** The role list, the language patterns, and the ICP block
are written for a product sold to PMs and designers. Every one of them should change to match what
you sell – that file is the configuration.

## Data, and what stays out of git

`data/` and `results/` are gitignored. The repo they came from committed both, which meant a target
list, per-company scan findings, and – because signal 4 snapshots a team page – the names and roles
of real people at those companies. None of that is in this repo, and the examples carry the column
contracts with invented rows.

That fourth signal deserves a moment’s thought before you run it. Diffing a public team page is
ordinary competitive research; keeping a dated store of named individuals and their job changes is a
small database of personal data, and it should live locally, be kept only as long as it is useful,
and never be published.

## Layout

```
CLAUDE.md      the scanner - signal definitions, scoring, tiers, commands
docs/          the original design spec, including what was deliberately left out
scripts/       the GitHub front-end activity scanner
examples/      seed and output CSVs with the real column contracts
data/          your seed and feedback files (gitignored)
results/       scan output, one archived JSON per run (gitignored)
```
