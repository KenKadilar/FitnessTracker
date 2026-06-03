# Home Fitness Tracker

A single-file PyQt6 desktop app for tracking diet (calorie checklist),
workouts, recipes, a food calorie calculator, and a weekly history overview —
with an embedded mobile PWA so you can check off items from your phone
without installing anything. All data lives on your own machine, plain
JSON, no cloud account.

## Features

- **Diet checklist** with per-day frozen snapshots, so editing today's
  template never rewrites yesterday's logged values.
- **Workout templates + history** (also snapshot-based for the same reason),
  HIIT timer with custom beep, in-tab rest timer.
- **Food calorie calculator** + a **recipes** tab with an in-place editor.
- **Daily Overview** — weekly grid showing diet template name, calories,
  deficit/surplus, and workouts at a glance.
- **Phone access via an embedded HTTP server + PWA** — installable on
  iOS/Android, full diet checklist + food/workout/recipes/history. Works on
  your LAN out of the box; an optional Cloudflare-tunnel path adds
  HTTPS-from-anywhere with email-PIN gating (see below).
- **PDF + Markdown exports** of diet and workout history.

## Tech

Python 3.12, PyQt6, stdlib `ThreadingHTTPServer`, vanilla JS PWA — no build
step, no framework, no cloud dependency. Optional: `cloudflared` for the
phone-from-anywhere path.

## Install & run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python health_tracker.py
```

That's it. The app creates a `DATA/HealthTracker/` folder next to the
script (or next to the `.exe` when packaged) for your diet logs, workout
history, recipes, foods, and templates. Edit the JSON files there directly,
or use the in-app editors.

## Build a standalone `.exe` (optional, Windows)

```powershell
pyinstaller --onefile --windowed --name HealthTracker `
  --icon icon.ico health_tracker.py
```

Keep `icon.ico` and `beep.wav` beside the resulting `.exe`; the app finds
them automatically via the same resolver that handles dev mode.

## Phone access

The desktop app embeds a tiny HTTP server on `0.0.0.0:20003` and serves an
installable PWA at `/`. **On your LAN**, point your phone's browser at
`http://<your-pc-lan-ip>:20003/` — the status bar shows the URL on launch.
The PWA covers: Diet Checklist (the main thing), Food Calculator,
Recipes, Workout Log, Diet & Workout History.

**For HTTPS from anywhere** (so the PWA actually installs as a real app),
the recommended path is a [Cloudflare named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
pointing `https://<your-subdomain>` → `http://localhost:20003`, gated by
[Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/applications/)
(email one-time PIN). The app auto-runs `cloudflared` when these are set in
a gitignored `DATA/HealthTracker/.env`:

```
CLOUDFLARE_TUNNEL_TOKEN=eyJ...        # from your tunnel's "Run" command
APP_PUBLIC_URL=https://your.subdomain # for the status-bar link
```

Set `PHONE_TUNNEL_ENABLED=0` (env var) to skip the tunnel and just use LAN.
Set `PHONE_SERVER_ENABLED=0` to disable the phone server entirely.

## Data layout

All user data is portable and lives next to the script/exe:

```
DATA/HealthTracker/
  recipes.json
  foods.json
  beep.wav                            # (resolver also finds it beside the script)
  DietTracker/
    diet_config.json                  # active diet
    diet_logs.json                    # per-day checklist logs (your history)
    diet_template_settings.json       # which template is "default"
    diet_configs/*.json               # selectable templates
  WorkoutTracker/
    workout_templates.json
    workout_history.json
  backups/    exports/                # auto-generated
  .env                                # optional secrets (tunnel token, etc.)
```

Copying or moving the folder takes your data with you. Files are
hand-editable JSON; the app normalizes defensively on load and backs up
anything it can't read.

## Architecture (one file, three layers)

1. **Module-level helpers** — parsing/formatting, snapshot logic, PDF/HTML
   export, workout template normalization.
2. **`UnifiedStore`** — single in-memory `self.data` dict that persists to
   separate JSON files under `DATA/HealthTracker/`.
3. **Qt UI pages** — one `QWidget` per tab; `MainWindow` wires them
   together plus the embedded HTTP server.

See [CHANGELOG.md](CHANGELOG.md) for the engineering log.

## License

MIT — see [LICENSE](LICENSE).
