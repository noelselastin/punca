# Punca task list

Workstreams follow README section 20. Assign names and points as a team. `[x]` = done in the repo, `[ ]` = open.

Deadlines (from the hackathon Discord, check #announcements for changes):
- **13 Nov 2026, 12:00 PM (noon) MYT**: prototype submission (title, challenge, 50+ character summary, HTTPS repo link, PDF pitch deck up to 10 MB, optional demo link). Final submission locks the entry.
- **15 Nov**: Top 5 announced. **16 Nov**: Top 5 integrate Gemini Enterprise. **17 Nov**: final pitch at APU Auditorium (must use Gemini Enterprise tools).

## Member 1: AI and diagnosis engine
- [x] Concept graph (37 nodes) and probe bank (88 probes), hand-written
- [x] BKT mastery update and frontier root-cause selection (`backend/diagnosis/`)
- [x] Concept mapping: BM25 shortlist + Gemini choice with a JSON schema, offline fallback
- [x] Grounded remediation with citations and a "not found in course material" fallback
- [x] Evaluation set (25 items) and runner; offline results in README section 15
- [x] Configure Gemini locally and record the live evaluation in README section 15 (25/25 mappings, 24/25 root causes; simulated development cases)
- [ ] Review a third of the graph edges and probes written by someone else (README section 20)
- [ ] Add 5 to 10 eval items written in real students' words (not tuned against)
- [ ] Top 5 only: plan the Gemini Enterprise integration (for example, register the tutor as an agent)

## Member 2: Cloud backend, data and scheduling
- [x] FastAPI service, request logging to `logs/punca.log`
- [x] Student sign-up and sign-in (local accounts); seeded demo staff login for the lecturer view
- [x] Study circle grouping, availability matching, lecturer slots, gap clinics
- [x] Stamps: verified tier on a passed re-check, endorsed tier by lecturer countersign
- [x] Synthetic seed data and BigQuery NDJSON export
- [ ] Deploy (Cloud Run + Firestore + Firebase Auth) once Google Cloud credits arrive; until then the demo runs locally
- [ ] Make the GitHub repo public before submitting, and confirm no secrets are committed (`.env` is git-ignored)

## Member 3: Frontend, content and pitch
- [x] Redesign the landing page: student hook, verified research, animated passport flight, peer-circle detour, re-check stamps, FAQ, and responsive layouts
- [x] Student UI: diagnose flow, result, remediation, practice, re-check, circles, history
- [x] Passport pages and map view, opt-in sharing
- [x] Lecturer dashboard: demand, heatmap, slot manager, confirm/decline, countersign, shared passports
- [x] Run the student survey (README section 1) and put real results in the README: 22 responses, November 2026 ([docs/survey-results.md](docs/survey-results.md))
- [ ] Pitch deck as PDF (10 MB or less) and a 3-minute demo run-through (README section 16)
- [ ] Optional demo link (screen recording or hosted build)

## Stretch (after the core demo works)
- [ ] Passport PDF export
- [ ] Mentor stamps and faded stamps
- [ ] Google Calendar free/busy sync
- [ ] Multilingual explanations
- [ ] Spaced re-testing reminders
- [ ] Decide the licence and add `LICENSE`
