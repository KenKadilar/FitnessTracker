# Changelog

All notable changes to Home Fitness Tracker.

## [0.1.0] — Initial public release

Single-file PyQt6 desktop app with these capabilities at v0.1:

- **Diet Checklist tab** — per-day item checklist with per-day frozen
  snapshots so editing today's template never rewrites yesterday's
  history. Items group by category, autosave on every change, support
  Turkish/European decimal comma and a tiny safe arithmetic mini-calculator
  (`120 + 33`, `(100+50)/2` — `ast`-based, never `eval`) on the "additional
  calories" and "additional deficit" fields. Multiple selectable diet
  templates via JSON files in `DietTracker/diet_configs/`.
- **Diet History tab** — list of saved days with summary, view per-day
  details, Markdown + PDF exports (all dates / last 7 / custom range),
  delete by date.
- **Workout Log + History tabs** — JSON-driven workout templates with a
  schema-flexible loader that preserves unknown fields through a
  round-trip. HIIT timer with custom `beep.wav`, in-tab strength rest
  timer. Editing a saved workout loads its frozen snapshot, not the
  current template.
- **Recipes tab** — built-in `RecipeEditDialog` for adding/editing/deleting
  recipes; per-recipe ingredients and totals; Markdown + PDF export.
- **Food Calculator tab** — kcal/g + arbitrary unit definitions
  (`{"g": 1.0, "medium banana": 118}`); live calculation on amount/unit
  change.
- **Daily Overview tab** — week-at-a-glance grid with diet template name,
  calorie totals, deficit/surplus, and workouts per day.
- **Phone access — installable PWA over an embedded
  `ThreadingHTTPServer`** on `0.0.0.0:20003`. All `/api/*` work goes
  through a `PhoneBridge` Qt signal queued onto the main thread, so the
  HTTP handler never touches widgets directly. Diet checklist with
  live-summary updates, food calculator (with search), recipes, workout
  log (name / amount / load / RiR / Save) with in-progress edits cached
  client-side across tab switches, diet & workout history (view + delete).
  Custom dark-styled checkboxes; today auto-refreshes on the phone's local
  clock. Pure store reads on every phone GET — the desktop's date and
  notes are never mutated by a phone refresh.
- **Optional Cloudflare named tunnel** for HTTPS-from-anywhere with
  email-PIN gating via Cloudflare Access. Auto-started by the app when a
  token is present in the gitignored `DATA/HealthTracker/.env`. The child
  process is placed in a Windows Job with `KILL_ON_JOB_CLOSE` (and a
  startup self-heal that token-matches any leftover cloudflared from a
  prior run) so a crashed or force-killed app can never leave an orphan
  tunnel serving 502.
- **Maskable launcher icon** generated at runtime from the app's `.ico`
  via PyQt (no Pillow dependency), full-bleed by design — the WebAPK
  icon fills the tile like a normal app rather than floating a small
  logo on a gradient.
- **PDF + Markdown exports** for diet history, workout history, and
  recipes (PyQt `QTextDocument` rendering; no extra dependency).
- **Defensive JSON loading**: every config / log / template file is
  normalized on read, and any unreadable file is backed up to
  `DATA/HealthTracker/backups/` before the app falls back to defaults —
  the app refuses to crash on bad data.

### Known limitations / planned for next versions

- The diet and workout templates are still edited primarily through the
  JSON files in `DATA/HealthTracker/`. A built-in **Diet Editor** and
  **Workout Editor** (mirroring the existing `RecipeEditDialog` shape) are
  the next milestone (v0.2).
- Daily Overview is desktop-only by design; the phone PWA covers the
  per-day workflow.
