# Git History Cleanup & Secret Rotation — Evidence and Checklist

**Repo:** `Enuma3lish/Vidgo_Gen_AI`
**Cleanup performed:** 2026-06-24 (see commit `e02583a` and the tag re-cut documented below)
**Document status:** Parts A & B are machine‑verified and reproducible. Part C is a
rotation checklist that **must be completed by the repository owner** — rotation
dates/platforms are operational facts this document cannot derive.

---

## Part A — History rewrite evidence (`git filter-repo`)

The history was rewritten with **`git filter-repo`** to purge `.claude/` (Claude
Code session data — `settings.local.json`, transcripts) from every commit on
every branch. The tool's run metadata is present under `.git/filter-repo/`:

| Artifact | Meaning |
|---|---|
| `.git/filter-repo/commit-map` | 226 commit hashes rewritten (227 lines incl. header) |
| `.git/filter-repo/ref-map` | old→new tip for each rewritten ref (table below) |
| `.git/filter-repo/changed-refs` | the 7 refs that were rewritten |
| `.git/filter-repo/first-changed-commits` | first commit where content diverged: `73b9dee` → `3f23a0f` |
| `.git/filter-repo/suboptimal-issues` | 27 short hashes referenced in *commit messages* of now‑rewritten commits were left as‑is (cosmetic only — no content impact) |
| `.git/filter-repo/already_ran` | marker proving the filter ran in this clone |

### Refs rewritten (old tip → new tip)

| Ref | Old | New |
|---|---|---|
| `refs/heads/main` | `63b6773` | `e02583a` |
| `refs/heads/claude/add-free-trial-mode-B21Bl` | `1ce7283` | `c379cd4` |
| `refs/heads/claude/ai-video-lead-gen-system-tf241h` | `5551d4c` | `3a74109` |
| `refs/heads/claude/eager-nash` | `2769e46` | `7e9559f` |
| `refs/heads/claude/fix-todo-ml6xh39predwxz71-aJc9c` | `49cd8bd` | `af8df39` |
| `refs/heads/feat/interior-exterior-design-tools` | `07d5139` | `5ecf85a` |
| `refs/heads/revert-1-claude/add-free-trial-mode-B21Bl` | `65d8ff0` | `489f916` |

The rewritten history was **force‑pushed** to `origin`, and **6 stale branches**
were deleted from the remote so no pre‑rewrite tips remain reachable. `main`
subsequently advanced past `e02583a` through normal commits (current `main` tip
contains it as an ancestor).

### Reproduce

```bash
ls -la .git/filter-repo/                 # run metadata present
cat   .git/filter-repo/ref-map           # old→new ref tips
cat   .git/filter-repo/changed-refs      # 7 rewritten refs
wc -l .git/filter-repo/commit-map        # 227 (226 commits + header)
```

---

## Part B — Verification: no secret files remain in history

All commands below were run across **all refs and full history** and return the
results shown.

### B1. No `backend/.env` ever committed
```bash
$ git log --all --full-history --oneline -- backend/.env
# (no output — never present in history)
```

### B2. No `.claude/` anywhere in history (post‑rewrite)
```bash
$ git log --all --full-history --oneline -- '.claude' '.claude/**' '**/.claude/**'
# (no output)
```

### B3. The only `*.env`‑named path in all history is a non‑secret QA status file
```bash
$ git rev-list --all | while read c; do git ls-tree -r --name-only "$c"; done \
    | grep -E '\.env$' | sort -u
TEST/qa_runs/20260511T190150Z/status.env
```
Its full historical content is shell **status flags**, not credentials, and it is
**not tracked in `HEAD`**:
```
admin_test_tools_shell_exit=1
admin_test_tools_report_written=true
browser_record_tools_exit=0
```

### B4. `.env` files tracked in `HEAD` are templates / public build vars only
```bash
$ git ls-files | grep -E '(^|/)\.env'
backend/.env.example          # placeholder template, no real values
frontend-vue/.env.development  # Vite build-time vars (public by design)
frontend-vue/.env.production   # Vite build-time vars (public by design)
```
`.gitignore` excludes real `.env` files; only the above non‑secret files are
tracked.

**Conclusion:** no credential‑bearing file exists in the current tree or anywhere
in rewritten history.

---

## Part C — Secret rotation checklist (OWNER TO COMPLETE)

Because `.claude/` session data was committed before the purge, treat **every
application secret as potentially exposed** and rotate it. This document **cannot
verify rotation** — fill in the platform, rotation date, and old‑key‑disabled
confirmation for each row. Source of truth for the secret set is
`backend/app/core/config.py` (values are injected at runtime, not stored in git).

> Legend: ⬜ not confirmed · ✅ rotated & old key disabled · ➖ n/a

| # | Secret (config key) | Platform to rotate on | Exposed? | Rotated (UTC date) | Old key disabled? | Notes |
|---|---|---|---|---|---|---|
| 1 | `SECRET_KEY` (JWT signing) | App / Secret Manager | ⬜ | | ⬜ | Rotating invalidates all sessions/JWTs |
| 2 | `DATABASE_URL` (Postgres creds) | Cloud SQL | ⬜ | | ⬜ | Rotate DB password |
| 3 | `PIAPI_KEY` | PiAPI dashboard | ⬜ | | ⬜ | |
| 4 | `POLLO_API_KEY` | Pollo.ai dashboard | ⬜ | | ⬜ | Generation backup provider |
| 5 | `WAN_API_KEY` | provider dashboard | ⬜ | | ⬜ | |
| 6 | `RUNWAY_API_KEY` | Runway dashboard | ⬜ | | ⬜ | |
| 7 | `A2E_API_KEY` | A2E.ai dashboard | ⬜ | | ⬜ | Avatar provider |
| 8 | `A2E_API_ID` | A2E.ai dashboard | ⬜ | | ⬜ | Paired with A2E_API_KEY |
| 9 | `TAIGI_TTS_API_KEY` | TTS provider | ⬜ | | ⬜ | |
| 10 | `ECPAY_HASH_KEY` | ECPay merchant console | ⬜ | | ⬜ | Payment signing |
| 11 | `ECPAY_HASH_IV` | ECPay merchant console | ⬜ | | ⬜ | Payment signing |
| 12 | `PAYPAL_CLIENT_ID` | PayPal developer dashboard | ⬜ | | ⬜ | Live app |
| 13 | `PAYPAL_CLIENT_SECRET` | PayPal developer dashboard | ⬜ | | ⬜ | Live app — high priority |
| 14 | `PAYPAL_WEBHOOK_SECRET` | PayPal developer dashboard | ⬜ | | ⬜ | Webhook `75T233837H582090M` |
| 15 | `S3_ACCESS_KEY` | S3/GCS HMAC console | ⬜ | | ⬜ | |
| 16 | `S3_SECRET_KEY` | S3/GCS HMAC console | ⬜ | | ⬜ | |
| 17 | `SMTP_PASSWORD` | mail provider | ⬜ | | ⬜ | |
| 18 | `RECAPTCHA_SECRET_KEY` | Google reCAPTCHA admin | ⬜ | | ⬜ | |

**Also confirm (not app config keys, but adjacent risk):**
- GCP service account key(s) for `vidgo-ai` — prefer Workload Identity / ADC over JSON keys; if any JSON key was ever in `.claude/` or local files, rotate it. ⬜
- Any OAuth/CI tokens (`gh`, Firebase CI) referenced during sessions. ⬜

When every row is ✅, this section is complete and the incident can be closed.

---

## Appendix — Tag note

The `v1.0.0` release tag was originally cut at `e02583a` (the first clean
post‑rewrite `main` tip) and later moved forward to the accepted release commit.
See repo tags for the current target.
