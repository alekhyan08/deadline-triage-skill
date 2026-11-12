# deadline-triage: a Hermes skill

A small, read-only [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill that ranks a supplied mailbox export by **explicit deadlines**.
Standard library only, no network, never sends or changes mail. It never guesses: anything incomplete or conflicting stays `needs_review`.

## Install as a skill tap
```
hermes skills tap add alekhyan08/deadline-triage-skill
hermes skills install alekhyan08/deadline-triage-skill/skills/deadline-triage
```
Then ask the agent things like "which of these emails have deadlines?" (it loads the skill and runs the helper), or run it directly:
```
python3 skills/deadline-triage/scripts/triage.py --input examples/sample_export.json          # JSON
python3 skills/deadline-triage/scripts/triage.py --input examples/sample_export.json --text   # readable list
```
Example (`--text`):
```
Deadline triage as of 2026-11-12 (America/Los_Angeles): 3 thread(s)
1. OVERDUE  2026-11-03  Design doc  [m3]  evidence: "2026-11-03"
2. DUE SOON  2026-11-13  * Report due soon  [m1]  evidence: "due by Friday, 13 November 2026"
3. NEEDS REVIEW  no explicit date  Newsletter  [m2]
```
## What it understands
`Deadline:` / `Due:` lines (ISO date, `today`, `tomorrow`), full-date phrases like "due by Friday, 13 November 2026 at 17:00", `Status: resolved` lines; the latest message in a thread wins; weekday/date mismatches are refused.

## Tests
`python3 -m unittest discover -s tests`

## License
MIT
