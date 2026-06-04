# Home Fitness Tracker

A single-file PyQt6 desktop app for tracking diet, workouts, recipes, and a
food calorie calculator, with an installable phone app (PWA) so you can tick
off your diet checklist from anywhere. All data lives on your own machine as
plain JSON; no cloud account.

<img width="1000" height="705" alt="fitness-tracker-demo" src="https://github.com/user-attachments/assets/1fb7d95b-0e49-49f8-8da8-a0d6bc422c41" />

## Features

- **Diet checklist** with per-day frozen snapshots, editing today's template
  never rewrites yesterday's logged numbers.
- **In-app editors** for diet and workout templates (plus recipes and foods),
  build, edit, rename, and delete everything from the UI; no JSON required.
- **Workout templates + history** with a HIIT timer and an in-tab rest timer.
- **Phone access** via an embedded server + installable PWA, works on your LAN
  out of the box, with an optional HTTPS-from-anywhere path.
- **Daily Overview** weekly grid, plus **PDF / Markdown exports**.

See [CHANGELOG.md](CHANGELOG.md) for the engineering log.

## Tech

Python 3.12, PyQt6, stdlib `ThreadingHTTPServer`, vanilla-JS PWA, no build
step, no framework, no cloud dependency.

## Install & run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python health_tracker.py
```

The app creates a portable `DATA/HealthTracker/` folder next to the script
(or beside the `.exe` when packaged) for your logs, history, recipes, and
templates, copy the folder to take your data with you. Manage everything from
the in-app editors; power users can also edit the JSON directly (the app
normalizes defensively and backs up anything it can't read).

## Phone access

The app serves an installable PWA on your LAN at `http://<your-pc-ip>:20003/`
(the URL shows in the status bar on launch), Diet Checklist, Food Calculator,
Recipes, Workout Log, and history. For HTTPS-from-anywhere, point a
[Cloudflare named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
at `http://localhost:20003` and set `CLOUDFLARE_TUNNEL_TOKEN` in a gitignored
`DATA/HealthTracker/.env`. Set `PHONE_SERVER_ENABLED=0` to disable the phone
server entirely.

## Build a standalone `.exe` (optional, Windows)

```powershell
pyinstaller --onefile --windowed --name HealthTracker `
  --icon icon.ico health_tracker.py
```

Keep `icon.ico` and `beep.wav` beside the resulting `.exe`; the app finds them
automatically via the same resolver used in dev mode.

## Architecture

One file, three layers: module-level helpers (parsing/formatting, snapshot
logic, PDF/HTML export) → **`UnifiedStore`**, one in-memory `self.data` dict
persisted to split JSON files under `DATA/HealthTracker/` → **Qt UI pages**,
one `QWidget` per tab, with `MainWindow` wiring them plus the embedded HTTP
server. See [CHANGELOG.md](CHANGELOG.md) for the deeper engineering narrative.

## License

MIT: see [LICENSE](LICENSE). Copyright (c) 2026 Can KADILAR.
