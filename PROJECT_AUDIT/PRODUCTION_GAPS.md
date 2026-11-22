# Production Gaps — consolidated checklist

Date 2026-11-22. Working tree = `bf1f44b` + the end-to-end validation changes (uncommitted). This list merges three
passes: the first audit, the end-to-end validation, and this production check. Items marked **(new)** were found in this
pass and verified by running or reading the code. Everything else was confirmed earlier and is still open.

Priority: **P0** blocks a public launch · **P1** needed for a dependable service · **P2** quality / later.
Effort: S < 1 day · M 1–5 days · L > 1 week. "Decision" = needs a product / owner choice before coding.

## P0 — must fix before going live

| # | Gap | Evidence | Effort |
|---|---|---|---|
| 1 | **Stored code execution**: legacy pages run JS from the world-writable Firestore `designs` collection in the app's origin | `firestore.rules:5-7`, `js/services/design-parser.js:155-195` (BUG-001) | S to lock the rules / remove pages · **Decision** |
| 2 | **No user accounts or ownership**: every visitor of `/` gets an editor session; anyone can edit or delete any design | `app.py:99-121`, `auth.py:127-141` (BUG-016) | M–L · **Decision** (auth provider) |
| 3 | **Legacy XSS sinks** (design names into `innerHTML`) and `Access-Control-Allow-Origin: *` on all non-API routes | `toast.js:16`, `design-browser.js:269,356`; `app.py:89-91` (BUG-014) | S (or retire legacy) |
| 4 | **(new) No security headers**: no CSP, X-Frame-Options, HSTS, X-Content-Type-Options, Referrer-Policy | grep of `app.py`, `board_api/` | S |
| 5 | **(new) Session cookie loses `Secure` behind a TLS proxy**: `secure=request.is_secure` with no `ProxyFix` | `app.py:108,120` | S |
| 6 | **(new) Generated API key written to the log in plain text** | `board_api/auth.py:91` | S |
| 7 | **(new) No production deployment setup**: no WSGI server (gunicorn/waitress) in requirements, no Dockerfile / Procfile / platform config, no CI. `python app.py` runs `debug=True` | `ls`, `app.py:304` | M |
| 8 | **(new) Unpinned dependencies, test tool in runtime requirements**: `flask>=3.0.0`, `pytest>=7.0` in `requirements.txt`, no lock file | `requirements.txt` | S |
| 9 | **Storage not safe for more than one worker**: design locks and rate limiter are per process; file store has no cross-process locking; on a read-only host it silently falls back to a temp dir | `store.py:37-41`, `auth.py:111`, `app.py:29-47` | M (use Firestore everywhere, or a shared lock) |
| 10 | **(new) Firestore 1 MiB document limit vs allowed design size**: each design is one document (one JSON string); ~135 curved boards exceed 1 MiB while the engine allows 300 boards × 2048 points | measured: 7.7 KB per 400-point board; `firestore_store._fields` | M (split components into sub-documents, or cap size with a clear error) |
| 11 | **(new) No backups** of designs (file store or Firestore) | no backup code or docs | S–M |
| 12 | **CNC routing not modelled**: no tool diameter, no inside-corner (dog-bone) relief, saw kerf applied to CNC cuts. "Ready for production" is optimistic for router-cut board | BUG-004 | M–L · **Decision** (which machines) |

## P1 — needed for a dependable service

| # | Gap | Evidence | Effort |
|---|---|---|---|
| 13 | **(new) API errors come back as an HTML page**: an unexpected exception in `/api/v1` returns `text/html` 500 | executed: injected exception → `500 text/html` | S |
| 14 | **(new) No health / readiness endpoint** for the platform or a load balancer | grep | S |
| 15 | No structured request logging, request ids, metrics or error tracking (Sentry etc.) | first audit 07 | S–M |
| 16 | **(new) Frontend production dependencies**: Tailwind's Play CDN (`cdn.tailwindcss.com`, which Tailwind documents as not for production) on 5 pages; no Subresource Integrity on any CDN script; three.js r128 (2021); app depends on 3 external CDNs being up | `grep` of `*.html` | M (bundle / self-host) |
| 17 | Compile is CPU-heavy and open to every session; rate limit is per process and per session (new sessions are free) | first audit 07; time budget now caps each request at 90 s | S–M |
| 18 | Product policy for requirement conflicts: `OVERALL_MISMATCH` is only a warning | BUG-007b · **Decision** | S |
| 19 | Weak attachments: a board hanging from one tab is not flagged; a tab deeper than the receiver is only a warning | SP-10, J-3 | S–M |
| 20 | Studio editor gaps: no add / resize / material editing, no undo UI, no restore button (API exists), no conflict-dialog browser test | 05, 07 | M |
| 21 | No hardware bill of materials (hinges, screws, dowels by size and count) | GAP-06 | S–M |
| 22 | Silent data loss at input: unknown JSON fields dropped without a message; requirements cut at 4000 chars without telling the user | E-1, E-2 | S |
| 23 | Validation and support computed twice per compile (+19 % compile time) | P-1 | S |
| 24 | Frontend has no automated tests beyond 5 headless-Chrome checks; backend coverage is 92 % | coverage run (this pass) | M |

## P2 — quality, scope and housekeeping

| # | Gap | Effort |
|---|---|---|
| 25 | Retire or isolate the legacy JS workbench (duplicate geometry / nesting / validation / 3D), `ai-prompt.txt` (served at 3 URLs), `scratch/` | M · **Decision** |
| 26 | **(new) No README or LICENSE** in the repository; `docs/architecture.md` describes only the legacy stack | S |
| 27 | **(new) No privacy policy / terms**, although user designs are stored (and the legacy collection is public) | S · **Decision** |
| 28 | Accessibility and internationalisation not audited | M |
| 29 | Nesting is bounding-box only (no true-shape / common-line cutting); DXF arcs become polylines with kerf compensation (BUG-017) | M–L |
| 30 | Format limits: no face-to-face joint in v1, no bevelled joints, no round stock or moving parts (documented in the AI prompt) | L · **Decision** |
| 31 | Direct Gemini / AI integration does not exist (prompt is copy-pasted). The repair / update prompts are the basis if it is wanted | M · **Decision** |
| 32 | **(new) Older dead code** flagged by pyflakes (unused imports in `canvas.py`, `validation.py`, `manufacturing.py`, `nesting.py`, `booklet.py`; unused variables) — reported, not removed | S |
| 33 | Studio requests `/favicon.ico` → 404 | S |
| 34 | The end-to-end validation work is uncommitted (21 modified + 9 new files) | S |

## Verified OK in this pass

* `pip-audit -r requirements.txt`: **no known vulnerabilities** in the declared dependencies (at today's resolved versions).
* Backend test coverage **92 %** (6517 statements; `support.py` 96 %, `canvas.py` 90 %, `routes.py` 92 %); 370 tests pass.
* Exports are refused (409) for designs that are not ready; floating boards, detached joints and sub-kerf holes now block production.
* No unbounded loops in the engine; every heavy request has a 90 s server budget and a 150 s client timeout.
* CSRF: cookie sessions require `SameSite=Strict` plus a custom header; API keys are checked per request.
* Fixed in this pass: Firestore version snapshots were never pruned and only the first 300 could be listed (my own
  addition from the validation). They now keep the last 100 like the file store and page through all of them
  (`test_firestore_versions_are_pruned_like_the_file_store`). My new test files were also made lint-clean.

## Suggested order

1. **Launch blockers you can do without a product decision (about 2–3 days):** #4, #5, #6, #7, #8, #11, #13, #14, and #3 if the legacy pages stay.
2. **Decisions first, then build:** #1 (lock or retire legacy), #2 (auth / accounts), #12 (which CNC machines), #10 (design size policy).
3. **Then:** #9 (multi-worker storage), #15–17 (observability, frontend bundling, abuse limits), and the P1 product items.
