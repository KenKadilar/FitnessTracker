# Changelog

All notable changes to Home Fitness Tracker.

## [0.6.0]: "Add food to notes" picker on the Diet Checklist

The Diet Checklist's log panel gains a food picker: search the foods from
`foods.json` / the Food Calculator, pick one from the dropdown, type a gram
amount, and click **Add to notes** (or press Enter in the grams box). It appends
a line like `Apple, 200 grams, 100 kcal. ` to the day's Notes (kcal = grams ×
`kcal_per_g`), each entry separated by a blank line, with a live `= N kcal`
preview before adding. The note autosaves.

## [0.5.1]: "Warm-up Notes" relabeled to "Notes"

The template-level note field is now labeled just **"Notes"** in the Workout
Log, Workout History detail, and the PDF/Markdown exports, since warm-ups are
now added as proper exercises (with the "No RIR" toggle) rather than living in
this field. Display label only; the `warmup_notes` / `_warmup_notes` JSON keys
are unchanged, so existing data keeps working.

## [0.5.0]: "No RIR" exercise toggle for warm-ups and mobility

- **Per-exercise "No RIR" toggle** in the Config Editor's Workout Templates
  editor. Flagging a warm-up or mobility move (wall slides, arm circles,
  bodyweight squats, stretches) sets a `no_rir` flag, and the Workout Log then
  disables the RIR (reps-in-reserve) box for that row, the same way it does for
  HIIT, but without the HIIT label or timer. Previously the only way to hide the
  RIR box was to mislabel the exercise as `(HIIT)`. `is_no_rir_exercise()` also
  honours an `exercise_type` of `mobility` / `warmup` / `no_rir`. The flag
  round-trips through the template JSON and saved history untouched.

## [0.4.0]: Reload workout templates; inline export confirmations

- **Workout Log "Reload templates" button**: re-reads `workout_templates.json`
  from disk and rebuilds the view, so edits made directly in the JSON or via
  the Config Editor show up without restarting (the workout-side counterpart to
  the Diet Checklist's "Reload config"). Bad JSON is backed up and the current
  in-memory templates are kept.
- **Inline export confirmations**: Diet History and Workout History show a brief
  "Exported: <file>" message next to the export buttons (for both Markdown and
  PDF) instead of a modal popup; failure dialogs are unchanged.

## [0.3.0]: Unified Config Editor, tray residence, and fixes

The diet and workout template editors are reworked into a single **Config
Editor** tab with three sub-editors (Foods, Diet Configs, Workout Templates),
replacing the per-tab "Edit template..." dialogs from 0.2.0. The editor pages
live in a small companion module, `config_editor.py`, that the main app embeds
as a tab and that also runs standalone.

- **Foods editor** (new): add, edit, duplicate, and delete entries in
  `foods.json` from the UI, including each food's unit-to-grams table and the
  file-level global units. Foods were previously editable only by hand.
- **Diet Configs editor**: pick any template file and edit its plan settings
  and item table (name / amount / unit / calories / category) plus the optional
  `display_label`, per-item notes, and `hide_amount_in_checklist`. Includes a
  split-item helper, a live plan-total vs target readout, "New template", and
  "Set as default". Templates are edited as raw JSON in place, so unknown fields
  round-trip untouched.
- **Workout Templates editor**: manage templates (add / rename / duplicate /
  delete) and edit each one's exercises, rest seconds, warm-up notes, and HIIT
  fields. Edited as raw JSON so schema-flexible and extra fields survive.
- Every save writes a timestamped backup first, and each editor has a "Reload
  from disk" button.

Also in this release:

- **System-tray residence**: the app starts hidden in the tray instead of
  keeping a permanent taskbar entry; closing the window hides it back, and Quit
  (tray menu or File -> Quit) is the only thing that exits. Includes an optional
  **run-at-startup** toggle (Windows registry / Linux autostart `.desktop`, as
  fully separate per-OS branches).
- **Linux startup fix**: force Qt off the glib event dispatcher so the app no
  longer busy-loops to 100% CPU when the audio socket is closed under it.
- **Calculator inputs** now normalize common Unicode lookalikes (fullwidth
  digits/operators, en/em dashes, Unicode minus, NBSP, zero-width characters)
  to ASCII before evaluating, and the error message names the offending
  codepoint when something still can't be parsed.

## [0.2.0]: In-app template editors

The diet and workout templates are now fully editable from the UI, no
JSON editing required. Built mirroring the existing `RecipeEditDialog`
shape.

- **Diet Editor** (`DietTemplateEditDialog`): an "Edit template..." button
  on the Diet Checklist tab opens an editor for the active template's
  target calories, estimated expenditure, notes, and item table
  (ID / Name / Amount / Unit / Calories / Category / Notes) with
  add / remove / move-up / move-down. Saving re-validates through
  `normalize_diet_config`, backs the file up first, and preserves unknown
  JSON fields. The per-day snapshot rule is upheld: editing a template only
  changes future blank days, saved days keep their frozen item / target /
  expenditure snapshots.
- **Workout Editor** (`WorkoutTemplateEditDialog`): an "Edit template..."
  button on the Workout Log tab edits exercises (Name / Sets × Reps /
  Target Load / Notes) plus the template's default rest seconds and warm-up
  notes. HIIT-block and other extra fields are exposed in an
  "Advanced (JSON)" column so they stay visible and editable, validated on
  save so HIIT data is never silently dropped; unknown fields round-trip
  via `ExerciseDef.extra`. Logged workouts keep their own snapshots.
- **Template management**: a "Manage ▾" menu on both tabs adds
  New / Rename / Delete. New opens the editor on an empty template; rename
  and delete keep the default-template and last-selected references in sync
  and leave saved history's frozen snapshots intact. The active
  `diet_config.json` fallback is protected from rename / delete.
- **First-run empty states**: the Workout Log tab shows a "Create your
  first template →" button instead of a JSON-editing instruction, and the
  Diet Checklist tab offers a "Create your first item →" button when a
  template has no items.
- README trimmed for a faster skim; JSON editing reframed as the
  power-user option rather than the default workflow.

## [0.1.0]: Initial public release

Single-file PyQt6 desktop app with these capabilities at v0.1:

- **Diet Checklist tab**: per-day item checklist with per-day frozen
  snapshots so editing today's template never rewrites yesterday's
  history. Items group by category, autosave on every change, support
  Turkish/European decimal comma and a tiny safe arithmetic mini-calculator
  (`120 + 33`, `(100+50)/2`, `ast`-based, never `eval`) on the "additional
  calories" and "additional deficit" fields. Multiple selectable diet
  templates via JSON files in `DietTracker/diet_configs/`.
- **Diet History tab**: list of saved days with summary, view per-day
  details, Markdown + PDF exports (all dates / last 7 / custom range),
  delete by date.
- **Workout Log + History tabs**: JSON-driven workout templates with a
  schema-flexible loader that preserves unknown fields through a
  round-trip. HIIT timer with custom `beep.wav`, in-tab strength rest
  timer. Editing a saved workout loads its frozen snapshot, not the
  current template.
- **Recipes tab**: built-in `RecipeEditDialog` for adding/editing/deleting
  recipes; per-recipe ingredients and totals; Markdown + PDF export.
- **Food Calculator tab**: kcal/g + arbitrary unit definitions
  (`{"g": 1.0, "medium banana": 118}`); live calculation on amount/unit
  change.
- **Daily Overview tab**: week-at-a-glance grid with diet template name,
  calorie totals, deficit/surplus, and workouts per day.
- **Phone access: installable PWA over an embedded
  `ThreadingHTTPServer`** on `0.0.0.0:20003`. All `/api/*` work goes
  through a `PhoneBridge` Qt signal queued onto the main thread, so the
  HTTP handler never touches widgets directly. Diet checklist with
  live-summary updates, food calculator (with search), recipes, workout
  log (name / amount / load / RiR / Save) with in-progress edits cached
  client-side across tab switches, diet & workout history (view + delete).
  Custom dark-styled checkboxes; today auto-refreshes on the phone's local
  clock. Pure store reads on every phone GET, the desktop's date and
  notes are never mutated by a phone refresh.
- **Optional Cloudflare named tunnel** for HTTPS-from-anywhere with
  email-PIN gating via Cloudflare Access. Auto-started by the app when a
  token is present in the gitignored `DATA/HealthTracker/.env`. The child
  process is placed in a Windows Job with `KILL_ON_JOB_CLOSE` (and a
  startup self-heal that token-matches any leftover cloudflared from a
  prior run) so a crashed or force-killed app can never leave an orphan
  tunnel serving 502.
- **Maskable launcher icon** generated at runtime from the app's `.ico`
  via PyQt (no Pillow dependency), full-bleed by design, the WebAPK
  icon fills the tile like a normal app rather than floating a small
  logo on a gradient.
- **PDF + Markdown exports** for diet history, workout history, and
  recipes (PyQt `QTextDocument` rendering; no extra dependency).
- **Defensive JSON loading**: every config / log / template file is
  normalized on read, and any unreadable file is backed up to
  `DATA/HealthTracker/backups/` before the app falls back to defaults,
  the app refuses to crash on bad data.

### Known limitations / planned for next versions

- The diet and workout templates are still edited primarily through the
  JSON files in `DATA/HealthTracker/`. A built-in **Diet Editor** and
  **Workout Editor** (mirroring the existing `RecipeEditDialog` shape) are
  the next milestone (v0.2).
- Daily Overview is desktop-only by design; the phone PWA covers the
  per-day workflow.
