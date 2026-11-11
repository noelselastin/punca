# Punca

> **Cari puncanya, bukan sekadar jawapannya.**
> *Find the cause, not just the answer.*

An AI-powered concept-gap diagnosis tool for STEM students. Punca traces what you are stuck on back to the earlier concept you are really missing, then connects you with peers and lecturers to close the gap.

*Punca* is Malay for "cause, origin, source", as in *punca masalah* ("root cause"). It is also the word for the source of a spring: the place where learning starts to flow.

Every student carries a **Punca Passport**: a personal booklet where each concept you verify earns a stamp, and each gap is marked "entry required" until you close it. Your passport shows where you have been; Punca shows the route to where you are stuck.

**Theme:** Smart Campus and Student Experience
**Event:** Google Cloud Hackathon, Asia Pacific University of Technology and Innovation (APU)
**Licence:** MIT (proposed; confirm before publishing)
**Status:** Hackathon build. Update the status table as parts land.

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [The Solution](#2-the-solution)
3. [How It Works](#3-how-it-works)
4. [Features](#4-features)
5. [The Student Passport](#5-the-student-passport)
6. [Status](#6-status)
7. [System Architecture](#7-system-architecture)
8. [Data Model](#8-data-model)
9. [The Diagnosis Engine](#9-the-diagnosis-engine)
10. [AI Design](#10-ai-design)
11. [Study Circles and Lecturer Connection](#11-study-circles-and-lecturer-connection)
12. [Privacy and Trust](#12-privacy-and-trust)
13. [Honest Limits](#13-honest-limits)
14. [MVP Scope and Roadmap](#14-mvp-scope-and-roadmap)
15. [Success Metrics](#15-success-metrics)
16. [Demo Script](#16-demo-script)
17. [Risks and Mitigations](#17-risks-and-mitigations)
18. [Run It](#18-run-it)
19. [Repo Guide](#19-repo-guide)
20. [Team and Work Split](#20-team-and-work-split)
21. [Licence](#21-licence)

---

## 1. The Problem

STEM modules are **cumulative**. A student who struggles with neural networks often has a weak spot two modules back: the chain rule, matrix multiplication, or basic probability. The student rarely knows this. They re-read the same slides, fall further behind, and lose confidence.

Why current support doesn't fix it:

- **Students** can't see the hidden prerequisite gap. They only see that "this lab is hard".
- **Lecturers** can't diagnose each student in large cohorts, and usually learn about gaps at exam time.
- **Generic AI tutors** answer the surface question ("explain backpropagation") without finding the real gap underneath.
- **Campus support** (consultations, peer tutoring, study sessions) exists, but students don't know which one they need, or when.

**The bottleneck:** nobody connects *"I'm stuck on this lab"* to *"you're missing this earlier concept, and here is the fastest way to fix it."*

### What APU students told us

In November 2026, 22 APU STEM students (Years 1 to 3) answered our Google Form, the *APU Student Learning Experience Survey*.

| Finding | Share |
|---|---|
| Have struggled with an advanced topic because they didn't fully understand an earlier concept | 82% (18 of 22) |
| Take a few days or more to realise the difficulty comes from an earlier concept, or sometimes never find it | 59% (13 of 22) |
| Rate their confidence in naming the concepts to revise at 3 or below out of 5 | 64% (14 of 22) |
| Turn to ChatGPT or another AI tool first when stuck (several answers allowed) | 95% (21 of 22) |
| Contact their lecturer first; attend consultation sessions | 9% (2 of 22); 0% |
| Would find a platform like Punca useful | 91% (20 of 22) |

> "Struggled with Advanced Fluid Mechanics due to weak foundations." (survey answer)

It is a small, self-selected sample. It shows the problem exists on our campus, not how common it is. Full results and every free-text answer are in [docs/survey-results.md](docs/survey-results.md).

## 2. The Solution

Punca takes what a student is stuck on, traces it through a **concept dependency graph**, runs a short adaptive diagnostic, and finds the **root-cause gap**. It then gives the student:

1. the shortest **remediation path** (explanation, practice, course resources), and
2. a way to **close the gap with other people**: study circles of students who share the same gap, scheduled against lecturer consultation slots.

For lecturers, Punca shows an **anonymized cohort heatmap**: which prerequisite gaps sit behind which labs and assignments.

## 3. How It Works

```
Student is stuck
      |
      v
[1] Submit stuck point   -> lab question / assignment brief / slide / free text
      |
      v
[2] Map to concepts      -> embeddings + LLM map the input to nodes in the concept graph
      |
      v
[3] Adaptive probes      -> 3-5 short questions on the target concept and its prerequisites
      |
      v
[4] Diagnose             -> mastery updated; deepest weak prerequisite = root cause
      |
      v
[5] Remediate            -> short explanation + practice + course notes (grounded, cited)
      |
      v
[6] Connect              -> join or create a Study Circle; book a lecturer or peer slot
      |
      v
[7] Re-check             -> quick re-test; pass it and the concept earns a stamp in your passport
```

## 4. Features

**Core (the single main feature): concept-gap diagnosis.** Steps 1 to 5 above. Everything else builds on it.

| Feature | Description | MVP |
|---|---|---|
| Concept map (passport pages) | Personal graph of mastery shown as passport pages: stamped (solid), shaky, entry required (gap), untested | Yes |
| Grounded remediation | Explanations and practice built from curated course material, with citations | Yes |
| Re-check loop | A short re-test after remediation updates mastery | Yes |
| Study Circles | Students with the same gap are grouped; common availability is found; a session is proposed | Yes (simplified) |
| Lecturer connection | Lecturers publish consultation slots, see anonymized demand, and confirm or open sessions | Yes (simplified) |
| Cohort heatmap | Most common root-cause gaps per module and lab | Yes |
| Student Passport | Verified concepts earn stamps; see section 5 | Yes |
| Lecturer endorsement | A lecturer can countersign a stamp after a circle session or consultation | Yes (simplified) |
| Passport export | Opt-in PDF summary of verified concepts, shareable with a lecturer or in an internship application | Stretch |
| Peer mentors | Students who mastered a concept can volunteer to help | Stretch |
| Calendar sync | Free/busy lookup and event creation via Google Calendar, with consent | Stretch |
| Multilingual explanations | Explanations in the student's preferred language | Stretch |
| Spaced re-testing | Reminders to re-check concepts before exams | Stretch |

## 5. The Student Passport

The passport is the **presentation layer** of the student's mastery state. It adds no new diagnosis logic: it turns progress into something students want to open, and gives the study circles and lecturer connection a visible purpose.

### The metaphor

| Passport idea | What it means in Punca |
|---|---|
| Passport page | A module (for example, AI Methods) |
| Region on a page | A cluster of related concepts (for example, Calculus Foundations) |
| **Stamp** (*cop*) | A concept the student has verified through a passed re-check |
| **Entry required** | A gap: the passport shows which concept to clear before moving on |
| Wrong turn | The root cause behind where the student got stuck |
| Route | The remediation path from the root cause to the target concept |
| Travel group | A Study Circle of students with the same gap |
| Countersignature | A lecturer endorsing a stamp |

### What a page looks like

```
+--------------------------------------------------------+
|  PUNCA PASSPORT                    Module: AI Methods  |
|  Holder: Student #A-0427                               |
|--------------------------------------------------------|
|  Region: Calculus Foundations                          |
|     [ Derivatives ]        [ Chain rule ]              |
|        STAMPED               ENTRY REQUIRED            |
|                                                        |
|  Region: Linear Algebra                                |
|     [ Dot product ]        [ Matrix multiplication ]   |
|        STAMPED               ENDORSED by lecturer      |
|--------------------------------------------------------|
|  Next destination: Backpropagation                     |
|  Route: Chain rule -> Gradient descent -> Backprop     |
+--------------------------------------------------------+
```

### Stamp rules

| Tier | How it is earned |
|---|---|
| **Verified stamp** | `pKnown` is above the threshold on a **re-check** after remediation. A first diagnosis alone never earns a stamp, so it can't be gamed by guessing once. |
| **Endorsed stamp** | A lecturer countersigns a verified stamp, for example after a study circle session or a consultation. |
| *Mentor stamp (Stretch)* | Awarded when a student with a stamp facilitates a circle on that concept. |
| *Faded stamp (Stretch)* | A stamp fades if later re-checks show mastery has dropped, prompting a refresher before exams. |

### Why it helps, beyond looking good

- **Visible progress** reduces the "am I missing something?" anxiety that STEM students often feel.
- **A clear next step:** an "entry required" mark points at exactly one concept, not a vague sense of falling behind.
- **A reason to join circles:** the lecturer's countersignature gives a session a visible outcome.
- **Optional proof (Stretch):** an opt-in PDF of verified concepts that students can share with a lecturer or attach to an internship application.

### Guardrails

- Stamps are **study aids, not grades or credentials**.
- Sharing a passport is **opt-in**; nothing is visible to lecturers or peers unless the student chooses.
- **No leaderboards** in the MVP, to avoid comparison pressure.
- Stamps come only from real re-checks. If the passport ever feels more important than the learning, cut animations before cutting diagnosis quality.

## 6. Status

This is a hack-day build. Nothing below is claimed as done until it is.

| Part | Owner | Status |
|---|---|---|
| Concept graph and probe bank (maths to ML chain) | All three | MVP done: 37 hand-written concepts, 88 probes, 37 course-note passages. Needs the cross-review in section 20. |
| Concept mapping and diagnosis engine | Member 1 | MVP done: keyword shortlist + Gemini choice; BKT mastery; frontier root cause. Gemini path not yet measured (no API key in the repo). |
| Grounded remediation (Vertex AI Search) | Member 1 | MVP done with local retrieval over `data/notes/` and citations; Vertex AI Search not wired. |
| Cloud setup, auth and API | Member 2 | API done (FastAPI). Student sign-up and sign-in done (local accounts). Cloud Run, Firestore and Firebase Auth not set up. |
| Study Circles and slot matching | Member 2 | MVP done (availability grid, lecturer slots, gap clinics). |
| Student UI and passport view (concept map as passport pages) | Member 3 | MVP done, including a public landing page (problem, sourced research figures, solution) and passport onboarding: create an account, then customise the passport (cover, emblem, name, goal, labs, privacy). |
| Stamp rules and endorsement | Members 1, 2 and 3 | Verified and endorsed tiers done. Mentor and faded stamps (Stretch) not started. |
| Lecturer dashboard and heatmap | Member 3 | MVP done, on synthetic cohort data. |
| Evaluation set and accuracy measurement | Member 1 | 25 simulated cases; offline and live Gemini results in section 15. |
| Survey and pitch | Member 3 | Survey done: 22 responses (section 1). Pitch video in progress. |

### What the MVP does differently from the plan

The plan in section 7 is the target. To run today with no cloud bill, the build makes these substitutions; each one sits behind a small module so it can be swapped later:

| Planned | In the MVP | Where to swap |
|---|---|---|
| Firebase Authentication | Email + password **student accounts** (salted PBKDF2 hashes, random session tokens). Students sign up in the app. There is no lecturer sign-up: the lecturer dashboard uses one seeded demo staff login. | `backend/auth.py`, `backend/api/service.py` |
| Firestore | A local JSON document store with the same collection names | `backend/store/local_store.py` |
| Gemini on Vertex AI | Gemini API free tier by default (`GEMINI_API_KEY`); set `USE_VERTEX=true` + `GCP_PROJECT` for Vertex AI. All model IDs are pinned. Default: `gemini-3.5-flash-lite` for mapping and explanations, with `gemini-3.1-flash-lite` as the fallback when a model is overloaded (503), rate-limited (429) or times out (504); a busy model is skipped for a minute (an hour after a daily-quota error). The UI shows which model answered. Why Flash-Lite: on the free tier (AI Studio, 9 Nov 2026) each Flash-Lite model allows 15 requests a minute and 500 a day, while `gemini-3.8-flash` allows 5 a minute and 20 a day. Switch `GEMINI_MODEL` once Google Cloud credits arrive. With no key it runs a deterministic offline mode. | `backend/llm/client.py` |
| Embeddings + Vertex AI Search | BM25 keyword retrieval for the concept shortlist and the course notes | `backend/retrieval/bm25.py` |
| BigQuery + Looker Studio | Heatmap computed in the API; events export as NDJSON for `bq load` | `backend/analytics/export_events.py` |
| LLM-generated probes | Hand-written probe bank only | `data/probes/` |

## 7. System Architecture

```
+-----------------------+       +----------------------------+
|  Web app (students)   |       |  Web app (lecturers)       |
|  React / Next.js      |       |  dashboard + slot manager  |
+-----------+-----------+       +-------------+--------------+
            |                                 |
            +----------------+----------------+
                             |
                    +--------v---------+
                    |  Firebase Auth   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   Cloud Run      |   API: diagnosis, circles, scheduling
                    |   (backend)      |
                    +--+------+------+-+
                       |      |      |
        +--------------+  +---+---+  +-----------------+
        |                 |       |                    |
+-------v------+   +------v--+  +-v---------------+  +-v-----------------+
| Gemini on    |   |Firestore|  | Vertex AI Search |  | BigQuery +        |
| Vertex AI    |   |(state)  |  | / RAG over notes |  | Looker Studio     |
+--------------+   +---------+  +------------------+  | (cohort heatmap)  |
                                                       +-------------------+
        Cloud Scheduler  -> reminders and re-check nudges
        Google Calendar API (Stretch) -> availability and event creation
```

| Layer | Technology |
|---|---|
| Frontend | React or Next.js, a graph library for the concept map |
| Auth | Firebase Authentication (student and lecturer roles) |
| Backend | Cloud Run (Python FastAPI or Node) |
| LLM | Gemini on Vertex AI, Flash tier; model ID set by environment variable |
| Retrieval | Vertex AI Search or RAG Engine over curated course notes |
| Embeddings | Gemini embedding model, to map stuck points to concepts |
| Database | Firestore |
| Analytics | BigQuery and Looker Studio |
| Scheduled jobs | Cloud Scheduler |

## 8. Data Model

Firestore collections (simplified):

```
courses/{courseId}
  name, code, moduleIds[]

concepts/{conceptId}
  name, description, courseId
  prerequisites: [conceptId, ...]
  resources: [{title, url, sourceId}]
  probeBank: [probeId, ...]

users/{uid}
  role: "student" | "lecturer"
  programme, year, courseIds[]
  availability: [{day, start, end}]
  consent: {shareNameWithCircle, shareNameWithLecturer}

mastery/{uid}_{conceptId}
  pKnown: number (0-1), lastUpdated, evidenceCount

diagnoses/{diagnosisId}
  uid, stuckInput, targetConceptId
  rootCauseConceptId, path: [conceptId, ...], createdAt

studyCircles/{circleId}
  conceptId, memberUids[], status: "forming" | "scheduled" | "done"
  proposedSlot, lecturerSlotId | peerMentorUid

lecturerSlots/{slotId}
  lecturerUid, courseId, start, end, capacity
  linkedConceptIds[], bookedCircleIds[]

stamps/{uid}_{conceptId}
  tier: "verified" | "endorsed"
  earnedAt, basedOnDiagnosisId
  endorsedByUid (optional), shareable: boolean
```

Anonymized analytics go to BigQuery as `diagnosis_events(courseId, targetConceptId, rootCauseConceptId, timestamp)`.

## 9. The Diagnosis Engine

The LLM **does not** decide the diagnosis alone. It generates and grades probes; plain code updates mastery and picks the root cause. That keeps results consistent and explainable.

### Concept graph

A directed acyclic graph. An edge `A -> B` means "B is a prerequisite of A".

```
Backpropagation
  -> Chain rule
       -> Derivatives
  -> Matrix multiplication
       -> Vectors and dot product
  -> Gradient descent
       -> Derivatives
```

For the MVP, one chain (maths foundations to machine-learning basics, about 30 to 50 nodes) is **curated by hand**. Gemini may draft nodes and edges from syllabi, but a person reviews every edge.

### Mastery update

Each concept keeps `pKnown`. After each probe answer, apply a Bayesian Knowledge Tracing style update:

```
# per-concept parameters (tunable): pGuess, pSlip, pLearn
if correct:
    posterior = pKnown*(1-pSlip) / (pKnown*(1-pSlip) + (1-pKnown)*pGuess)
else:
    posterior = pKnown*pSlip / (pKnown*pSlip + (1-pKnown)*(1-pGuess))

pKnown = posterior + (1 - posterior) * pLearn
```

### Root-cause selection

1. Start at the concept(s) the stuck point maps to.
2. Probe the target. If mastery is low, probe its prerequisites (breadth-first, at most 5 probes in total).
3. The **root cause** is the weak concept (`pKnown` below a threshold) whose own prerequisites all look solid: the *frontier of weakness*.
4. The **remediation path** runs from the root cause back up to the target.

### Concept mapping

Embed concept names and descriptions, embed the student's stuck input, retrieve the top candidates, and let the LLM choose and justify using a strict JSON schema.

## 10. AI Design

- **Model:** Gemini on Vertex AI, Flash tier for all steps. A Flash-Lite model may be used for routing.
- **Pin the model version.** Read it from an environment variable (`GEMINI_MODEL`). Do not use `-latest` aliases, because their behaviour can change without notice. Check which models are available in Model Garden for your project.
- **Structured outputs only.** Every LLM call returns JSON matching a schema, so the UI never parses free text.
- **Low temperature** for grading and mapping; moderate for explanations.
- **Grounding.** Remediation comes from retrieved course notes and must cite a source. If nothing relevant is found, the system says so instead of inventing content.
- **Evaluation set.** Keep 20 to 30 test stuck-points with the expected root cause, and re-run them whenever prompts or the model change.

Example probe:

```json
{
  "conceptId": "chain-rule",
  "question": "If f(x) = (3x + 1)^2, what is f'(x)?",
  "type": "multiple_choice",
  "options": ["...", "...", "...", "..."],
  "correctIndex": 2,
  "difficulty": 2,
  "misconceptionTags": ["forgot-inner-derivative"]
}
```

Example diagnosis result:

```json
{
  "targetConceptId": "backpropagation",
  "rootCauseConceptId": "chain-rule",
  "confidence": 0.78,
  "evidence": [{"probeId": "p12", "correct": false, "misconception": "forgot-inner-derivative"}],
  "remediationPath": ["chain-rule", "gradient-descent", "backpropagation"],
  "explanationSources": ["lecture-notes-wk3.pdf#p4"]
}
```

## 11. Study Circles and Lecturer Connection

Knowing the gap is half the solution. Punca turns each diagnosis into a **scheduled, supported session**.

### Flow

1. **Grouping.** When several opted-in students share the same root-cause concept, Punca proposes a **Study Circle** (target size 3 to 6).
2. **Finding a time.** Students enter weekly availability in a simple grid; Punca finds the overlap. *(Stretch: read free/busy from Google Calendar with explicit consent.)*
3. **Lecturer connection.** Lecturers publish consultation slots (time, capacity, linked concepts). Punca suggests the best-matching slot per circle. A lecturer can **confirm**, **open an extra "gap clinic"** when demand is high, or **attach resources**.
4. **Peer mentors (Stretch).** Students who mastered the concept can volunteer to facilitate.
5. **Session and re-check.** After the session, members re-test, mastery updates, and the circle closes.

### What lecturers see

- **Demand view:** counts only, such as "12 students need a chain-rule refresher before Lab 5".
- **Slot manager:** create slots, see circles requesting them, confirm or decline.
- **Opt-in identification:** names appear only if students choose to share them.

### Matching logic (MVP)

```
for each concept C with at least minGroupSize opted-in students:
    group = students whose rootCause == C
    commonSlots = intersect(availability of group members)
    candidates = lecturerSlots linked to C, inside commonSlots, with capacity >= |group|
    propose best candidate (earliest, best capacity fit); otherwise propose a peer-only slot
```

## 12. Privacy and Trust

- **Opt-in by default** for circles and for sharing identity with lecturers.
- **Anonymized lecturer analytics:** aggregates only, with a minimum count before any figure is shown.
- **Not a grading tool.** Mastery scores are never used for assessment.
- **Data minimisation:** store concept-level mastery, not long personal submissions.
- **Transparency:** every diagnosis shows its evidence, and students can correct it ("I actually know this").
- **No invented course content:** answers are grounded with citations, with a visible "not found in course material" fallback.
- **Demo data is fake.** The repo uses synthetic data only. Do not commit real student data, and confirm with APU before using any.

## 13. Honest Limits

- Punca helps find likely gaps; it is not a certified assessment. A diagnosis can be wrong, so students can correct it.
- Accuracy depends on how well the concept graph and probes are curated. The MVP covers one chain, not all of STEM.
- A small number of probes gives a probabilistic estimate, not proof of understanding.
- Study circles and lecturer slots in the MVP use a simple availability grid, not live calendar integration.
- The cohort heatmap in the demo uses synthetic data. Real figures need real usage.
- Stamps are study aids, not credentials or grades. They show only what a student has verified for themselves.
- Results will be reported in this README as real numbers once measured. Until then, metrics are targets, not results.

## 14. MVP Scope and Roadmap

**In scope**

- One curated concept chain (about 30 to 50 nodes) with a probe bank
- Stuck-point input, mapping, adaptive diagnosis, and cited remediation
- Student passport: concept map shown as passport pages, with stamps earned after a passed re-check
- Study Circle creation with availability-grid matching
- Lecturer slot publishing, circle-to-slot suggestions, and confirm action
- Lecturer countersign on a stamp (endorsed tier)
- Lecturer cohort heatmap (synthetic data)

**Out of scope for the hackathon**

- Integration with APU's real systems (portal, timetable, Moodle)
- Full multi-module coverage
- Automatic room booking
- University SSO

| Phase | Focus |
|---|---|
| Phase 1: Prototype | Concept graph, diagnosis engine, cited remediation, student UI |
| Phase 2: Connect | Study Circles, availability matching, lecturer slots and dashboard |
| Phase 3: Harden | Evaluation set, accuracy tuning, privacy review, accessibility |
| Phase 4: Expand | More modules, Calendar sync, peer mentors, spaced re-testing, multilingual support, LMS integration |

## 15. Success Metrics

Targets for a pilot; set realistic numbers after testing.

- **Diagnosis accuracy:** share of evaluation stuck-points where the expected root cause is found
- **Time to insight:** time from "I'm stuck" to a named root cause
- **Learning gain:** pre/post difference on the diagnosed concept
- **Circle conversion:** share of proposed circles that actually meet
- **Lecturer value:** whether lecturers act on the heatmap
- **Student trust:** survey rating of "the diagnosis matched my real gap"

### Measured so far (25 simulated cases)

Both runs used the 25 stuck-points in `data/eval/stuck_points.json` on 9 Nov 2026. The retained `data/eval/last_run.json` is the live Gemini run completed at 15:51 MYT; it superseded the earlier offline output. The offline baseline was measured with `python -m data.eval.run --offline`.

| Metric | Offline baseline | Live Gemini (`gemini-3.5-flash-lite`) |
|---|---|---|
| Stuck text mapped to the expected concept | 25 / 25 | 25 / 25 |
| Root cause found, starting from the expected concept | 24 / 25 | 24 / 25 |
| Root cause found, end to end | 24 / 25 | 24 / 25 |
| Probes used per diagnosis (mean) | 3.92 | 3.92 |
| Items answered by Gemini | 0 / 25 | 25 / 25 |
| LLM errors | Not applicable | 0 |

Read these carefully:

- The "students" are **simulated**: each one is missing exactly one concept and answers everything else correctly. Real students guess and slip, so real accuracy will be lower.
- The keyword list for Backpropagation was edited once after item e01 failed, so the mapping score is partly tuned to this same set. Wording from real students will score lower.
- The one miss (e19) is a known limit: the gap (matrix multiplication) sits two levels below the target behind three other prerequisites, and the 5-probe budget runs out first.
- All 25 live rows report `mappingSource: gemini`; none used keyword fallback. This is the same small development set, not held-out validation or evidence of improved real-student outcomes.
- To repeat the live evaluation, use `python -m data.eval.run --sleep 4` with a locally configured API key. This consumes API quota and replaces `last_run.json`; preserve the previous result first if you need to compare runs.

### Landing page and evidence

The landing page introduces the problem, links published evidence, and illustrates a learning flight through passport checkpoints. The example visits a study circle, returns to re-check the chain rule, and earns a stamp before continuing. It is labelled as an illustration. Visitors can pause, replay, or select steps; reduced-motion users get a static, manually selectable journey. The page uses a navy, warm-paper and gold palette, a cited research quote, and an accessible FAQ.

**Create my passport** keeps the existing journey: student sign-up, passport customisation, then the issued passport. Signed-in students return to their passport; staff return to the lecturer dashboard.

See [the landing-page evidence notes](docs/landing-evidence.md) for the source context and claims excluded from the supplied research draft. Published statistics describe external research, not APU students or measured Punca outcomes. The APU figures on the page come from the team's own survey ([docs/survey-results.md](docs/survey-results.md)).

## 16. Demo Script (about 3 minutes)

1. **The problem (30s).** A student fails a neural-network lab and re-reads the slides three times. Show the survey result.
2. **Diagnosis (60s).** Paste the lab question. Punca maps it, asks 4 quick probes, and reveals: *"Your gap isn't backpropagation. It's the chain rule."* The concept map shows the red node.
3. **Remediation (30s).** A short, cited explanation and 3 practice questions; a re-check turns the node amber, then green, and **a stamp lands in the passport**.
4. **Connect (40s).** Punca shows other students with the same gap, proposes a circle, and suggests a lecturer slot. The lecturer confirms, and later countersigns the stamp.
5. **Lecturer view (20s).** The heatmap shows the top cohort gaps before the next lab.

## 17. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Wrong diagnosis erodes trust | Hand-curated graph, deterministic mastery update, visible evidence, student can correct |
| LLM invents course content | Retrieval grounding with citations; explicit "not found" fallback |
| Model behaviour changes | Pinned model version via environment variable; evaluation set re-run on changes |
| Scope creep | Fixed MVP list; stretch items only after the core demo works |
| Low lecturer adoption | Show immediate value (heatmap, filled consultation slots); keep their workload small |
| Privacy concerns | Opt-in, anonymized aggregates, synthetic demo data |
| Cold start in the demo | Seed realistic synthetic cohort data and label it as synthetic |
| Passport looks like a gimmick | Stamps come only from real re-checks; lead the pitch with the problem, then show the passport as the result |

## 18. Run It

**Requirements**

- Python 3.11 or newer, and Node 20 or newer
- Optional: a Gemini API key from Google AI Studio (free tier, no billing). Without one, Punca runs in offline mode: keyword mapping and course notes shown as written.
- Later (planned architecture): a Google Cloud project with Vertex AI, and a Firebase project

**Setup**

```bash
git clone https://github.com/noelselastin/study-assistant.git
cd study-assistant

cp .env.example .env          # Windows: copy .env.example .env
# optional: put your GEMINI_API_KEY in .env (GEMINI_MODEL is pinned there too)

# backend (terminal 1)
cd backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload # http://127.0.0.1:8000

# frontend (terminal 2)
cd frontend
npm install
npm run dev                   # open http://localhost:5173
```

On first start the backend seeds synthetic demo data into `backend/var/store.json` (not committed). To start over: `python -m store.seed --reset` from `backend/` (stop the server first).

**Accounts**

- Visitors land on the public page. **Create my passport** leads to a student sign-up, then to passport customisation.
- The research figures on the landing page come from published sources, listed and linked at the bottom of that page. They are not APU data. The APU survey results (section 1) appear below them, under "We asked 22 APU STEM students".
- The sign-in page also has two demo buttons: **Try the demo student** and **Lecturer view (demo staff)**. Their logins are defined in `backend/store/seed.py` and exist only in the local demo store.
- There is no lecturer sign-up. Lecturer accounts would come from the university later.

**Tests and evaluation** (from the repo root, with the backend virtual environment active)

```bash
python -m pytest                     # 21 tests: engine, content checks, accounts, passport, full demo flow
python -m data.eval.run --offline    # evaluation set without an LLM
python -m data.eval.run              # same, using Gemini when GEMINI_API_KEY is set
```

**Logs.** The backend writes every request, error and browser-side error to `logs/punca.log`. Check it first when something fails.

## 19. Repo Guide

| Path | What it is |
|---|---|
| `frontend/` | Student and lecturer web apps (React + Vite) |
| `backend/api/` | Cloud Run service (FastAPI): routes in `factory.py`, logic in `service.py` |
| `backend/auth.py` | Student accounts: password hashing and session tokens |
| `backend/diagnosis/` | Mastery update and root-cause selection |
| `backend/llm/` | Prompts, schemas and the Gemini client (with offline fallback) |
| `backend/retrieval/` | BM25 search over concepts and course notes |
| `backend/scheduling/` | Circle grouping and slot matching |
| `backend/store/` | Local document store and synthetic seed data |
| `backend/analytics/` | Event export for BigQuery |
| `backend/tests/` | Automated tests |
| `data/concepts/` | Concept graph (JSON) |
| `data/probes/` | Probe bank (JSON) |
| `data/notes/` | Curated course notes used for cited remediation |
| `data/eval/` | Evaluation stuck-points and runner |
| `infra/` | Deployment configuration |
| `docs/` | Architecture diagrams, survey results, pitch |
| `TASKS.md` | Team task list and work split |
| `LICENSE` | MIT (proposed) |

## 20. Team and Work Split

Three members, 21 points of work each (full list in `TASKS.md`).

| Member | Workstream | Main responsibilities |
|---|---|---|
| Member 1 | AI and diagnosis engine | Concept mapping, probe generation and grading, mastery and root-cause logic, cited remediation, evaluation set, model configuration |
| Member 2 | Cloud backend, data and scheduling | GCP setup, Firestore and auth, API, study-circle grouping, availability and lecturer-slot matching, BigQuery export and seed data |
| Member 3 | Frontend, content and pitch | Student UI, concept map, circle and availability UI, lecturer dashboard, survey, demo and slides |

Each member also curates about a third of the concept graph, and a different member reviews it.

| Name | Role |
|---|---|
| *TBD* | Member 1 |
| *TBD* | Member 2 |
| *TBD* | Member 3 |

## 21. Licence

MIT (proposed). Add a `LICENSE` file before publishing.

---

*Punca was designed for the APU Google Cloud Hackathon. Course content, student data and cohort figures in the demo are synthetic or curated for demonstration.*
