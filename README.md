# deadline-triage: a Hermes skill

A small, read-only Hermes skill that ranks supplied mailbox exports by explicit deadlines.
It uses only the Python standard library, makes no network calls and never sends or changes mail.

- Understands `Deadline:` / `Due:` lines (ISO date, `today`, `tomorrow`), `Status: resolved` lines and full-date phrases such as "due by Friday, 13 November 2026".
- The latest message in a thread wins; ambiguous or incomplete dates stay `needs_review` (it never guesses).

## Install as a Hermes skill tap
```
hermes skills tap add alekhyan08/deadline-triage-skill
hermes skills install deadline-triage
```
## Try it
```
python3 skills/deadline-triage/scripts/triage.py --input examples/sample_export.json
```
