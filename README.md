# Amiranet Trainer · مدرّب أميرنت

A study web app for **Amiranet (אמירנט)** — the computerised English placement exam used by
Israeli universities, scored 50–150. Arabic-first interface, full English translation, spaced
repetition, timed mock exams, and an optional AI tutor.

**Live:** https://amiranet-trainer.netlify.app

---

## What it does

| Feature | Detail |
|---|---|
| **Vocabulary** | 359 exam-level words across 4 difficulty-ordered levels, each with an Arabic gloss, a worked example sentence, and synonyms |
| **Spaced repetition** | Leitner system, 5 boxes: 1 → 3 → 7 → 14 → 30 days. Wrong answers return to box 1 and reappear in the same session |
| **Level gating** | A level test of 15–20 mixed-format questions; 80% unlocks the next level |
| **Skill practice** | Every question in the bank regrouped by type — sentence completion, restatement, reading — into 13 untimed levels with instant feedback, so each skill is trained before it is tested |
| **Mock exams** | 5 full exams in the real Amiranet structure — 6 sections, 23 questions, 39 minutes |
| **Per-section timers** | Each section runs its own clock and **locks when it expires**, matching the real exam |
| **Scoring** | Mistakes → score on the published 50–150 conversion curve, with the exemption threshold marked |
| **AI tutor** | After an exam, wrong answers are listed and explained one tap at a time |
| **Planner** | Exam-date countdown, month calendar, per-day tasks |
| **Bilingual** | Arabic (RTL) ⇄ English (LTR) — layout direction, numerals, month names, and the tutor's own language all switch |

All vocabulary and exam content was written specifically for this project. No third-party
material is redistributed.

---

## Architecture

A single HTML file with **two interchangeable backends, selected at runtime**:

```
                    ┌─────────────────────────┐
                    │   src/app.template.html │
                    └───────────┬─────────────┘
                                │  build.py injects data/*.json
                                ▼
                    ┌─────────────────────────┐
                    │        app.html         │
                    └───────────┬─────────────┘
                    ┌───────────┴───────────┐
                    ▼                       ▼
        Claude Artifact runtime      Static host + Supabase
        (claude.use('db'/'sample'))  (auth, Postgres, Edge Function)
                    └───────────┬───────────┘
                                ▼
                    localStorage fallback
```

The page detects its environment on load and picks a storage adapter. One codebase, no
divergence between deployments, and it degrades to local-only storage when neither backend
is reachable.

### Data isolation

Every row is scoped by **Postgres Row Level Security**, not by client code:

```sql
create policy app_state_own on public.app_state
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);
```

A user tampering with the page in their own browser still cannot read anyone else's data.

### Protecting the API key

Signup is open, so the AI tutor is a **Supabase Edge Function**, never a key in the page:

- the LLM key lives in project secrets and never reaches the browser
- the caller's JWT is **verified server-side** — the presence of a header is not enough
- an atomic Postgres counter enforces a per-user daily quota **before** any paid call
- the quota table has RLS enabled with no policy, so only the server can touch it

---

## Stack

**Frontend** — one HTML file, no framework, no build toolchain. Google Fonts (Poppins for
Latin, Almarai for Arabic — ordered in one stack so each script resolves to its own face).

**Backend** — Supabase: Postgres, email/password auth, Edge Functions (Deno).

**Hosting** — any static host. Currently Netlify.

**Tooling** — Python 3, standard library only.

---

## Running it

```bash
git clone <this-repo>
cd Amirnet
python update.py          # generates data, builds both variants, packages the site
```

`update.py` runs three steps and stops at the first failure:

| Script | Does |
|---|---|
| `parse_book.py` | Reads `data/vocab_extra*.json` and `data/exams_generated.json`, sorts vocabulary by difficulty into levels, validates every exam (6 sections, 23 questions, answer key aligned) |
| `build.py` | Injects the generated JSON into the HTML template |
| `build_web.py` | Wraps it in a page shell, validates `config.js`, and zips it for upload |

### Deploying your own instance

1. Create a Supabase project and run `supabase/schema.sql` in the SQL editor
2. Copy `web/config.example.js` → `web/config.js`, fill in the Project URL and anon key
3. `python update.py`
4. Upload `amirnet-site.zip` to any static host
5. Set the site URL under Supabase → Authentication → URL Configuration

The AI tutor is optional — see `DEPLOY.md`. Without it the tutor hides itself and everything
else works.

---

## Notes from building it

**Column drift in PDF extraction.** The source dictionary was a two-column PDF. Default text
extraction shifted the Arabic column one row against the English, so `Alert` came out meaning
"changes" instead of "warning" — silently, for every entry after a blank line. Extracting in
table mode reads columns by position and fixes the alignment. The lesson: verify a sample
against the original before trusting several hundred extracted rows.

**Questions that reference line numbers.** Reading passages ask about "line 7" literally, so
line numbering is content, not decoration. Passages are stored as numbered line arrays and
rendered with a gutter every fifth line, matching the printed original.

**Practice before pressure.** The same 115 questions serve two modes. In a mock exam they run
under a per-section clock that locks on expiry; in practice they are regrouped by skill, untimed,
and marked the instant you answer. Reading is split by passage rather than by count, since a
passage and its questions are one unit.

**Measuring question difficulty instead of guessing.** The first generated exams felt right
but measured wrong: restatement options averaged 8.8 words against 14.7 in the reference
exams — materially easier, because short options are faster to eliminate. All 30 restatement
questions were rewritten to 13.7.

**RTL that actually flips.** Setting `dir="ltr"` was not enough: a `direction: rtl` rule in
the stylesheet outranks the attribute, so the layout stayed mirrored while the text turned
English. The fix is an inline direction plus logical (`text-align: start`) rather than
physical alignment throughout.

---

## Layout

```
├─ src/app.template.html     the whole application
├─ data/
│  ├─ vocab_extra*.json      vocabulary source
│  ├─ exams_generated.json   exam source
│  └─ difficulty.json        manual difficulty tiers, 1–6
├─ supabase/
│  ├─ schema.sql             tables, RLS policies, quota function
│  ├─ tutor.ts               Edge Function for the AI tutor
│  └─ stats.sql              usage queries
├─ web/config.example.js     template for your keys
├─ update.py                 one command: generate → build → package
├─ DEPLOY.md                 deployment guide (Arabic)
└─ HOWTO.md                  content-editing guide (Arabic)
```
