
import ast
import json
import html
import os
import re
import atexit
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QDate, Qt, QMarginsF, QTimer, QEvent, QUrl,
    QObject, pyqtSignal, QByteArray, QBuffer, QIODevice, QSize,
)
from PyQt6.QtGui import (
    QAction, QColor, QFont, QIcon, QTextDocument, QPageLayout, QPageSize,
    QPixmap, QPainter,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QHeaderView,
)
from PyQt6.QtPrintSupport import QPrinter

try:
    from PyQt6.QtMultimedia import QSoundEffect
except Exception:  # QtMultimedia may be unavailable in some PyQt installs; fallback uses QApplication.beep().
    QSoundEffect = None  # type: ignore

APP_TITLE = "Home Fitness Tracker"
APP_VERSION = "0.2"
APP_ICON_FILE = "icon.ico"
BEEP_SOUND_FILE = "beep.wav"
DATA_DIR_NAME = "DATA"
HEALTH_DATA_DIR_NAME = "HealthTracker"
DIET_DATA_DIR_NAME = "DietTracker"
WORKOUT_DATA_DIR_NAME = "WorkoutTracker"

DIET_CONFIG_FILE = "diet_config.json"
DIET_LOGS_FILE = "diet_logs.json"
DIET_CONFIG_TEMPLATES_DIR_NAME = "diet_configs"
DIET_TEMPLATE_SETTINGS_FILE = "diet_template_settings.json"
WORKOUT_TEMPLATES_FILE = "workout_templates.json"
WORKOUT_HISTORY_FILE = "workout_history.json"
RECIPES_FILE = "recipes.json"
FOODS_FILE = "foods.json"


DEFAULT_DIET_CONFIG: Dict[str, Any] = {
    "config_version": 1,
    "target_calories": 1800,
    "estimated_expenditure": 2000,
    "notes": (
        "Example starter template. Replace these items with your own foods, "
        "supplements, and targets — either through the app's editor or by "
        "editing DATA/HealthTracker/DietTracker/diet_config.json directly."
    ),
    "items": [
        {"id": "water_morning",  "name": "Water (morning)",      "amount": 500, "unit": "ml",      "calories": 0,   "category": "Hydration"},
        {"id": "water_midday",   "name": "Water (midday)",       "amount": 500, "unit": "ml",      "calories": 0,   "category": "Hydration"},
        {"id": "water_evening",  "name": "Water (evening)",      "amount": 500, "unit": "ml",      "calories": 0,   "category": "Hydration"},
        {"id": "daily_multivit", "name": "Daily multivitamin",   "amount": 1,   "unit": "tablet",  "calories": 0,   "category": "Supplements"},
        {"id": "breakfast",      "name": "Breakfast",            "amount": 1,   "unit": "meal",    "calories": 450, "category": "Meals"},
        {"id": "lunch",          "name": "Lunch",                "amount": 1,   "unit": "meal",    "calories": 600, "category": "Meals"},
        {"id": "dinner",         "name": "Dinner",               "amount": 1,   "unit": "meal",    "calories": 550, "category": "Meals"},
        {"id": "snack_fruit",    "name": "Fruit snack",          "amount": 1,   "unit": "serving", "calories": 100, "category": "Snacks"},
        {"id": "snack_nuts",     "name": "Nuts (small handful)", "amount": 30,  "unit": "g",       "calories": 180, "category": "Snacks"},
    ],
}


DEFAULT_RECIPES: Dict[str, Any] = {
    "schema_version": 1,
    "recipes": [
        {
            "id": "oatmeal_breakfast_bowl",
            "name": "Oatmeal Breakfast Bowl",
            "total_amount": 365,
            "unit": "g",
            "total_calories": 410,
            "notes": "Example starter recipe. Replace with your own.",
            "ingredients": [
                {"name": "Rolled oats, dry", "amount": 50,  "unit": "g", "calories": 190},
                {"name": "Milk, low-fat",    "amount": 250, "unit": "g", "calories": 125},
                {"name": "Banana, sliced",   "amount": 50,  "unit": "g", "calories": 45},
                {"name": "Honey",            "amount": 15,  "unit": "g", "calories": 50},
            ],
        },
    ],
}


DEFAULT_FOODS: Dict[str, Any] = {
    "schema_version": 1,
    "notes": (
        "Food calorie database for the Food Calculator tab. "
        "kcal_per_g means calories per 1 gram. Units convert an entered unit into grams."
    ),
    "global_units": {
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
    },
    "foods": [
        {
            "id": "banana_raw",
            "name": "Banana, raw",
            "kcal_per_g": 0.89,
            "default_unit": "g",
            "units": {"g": 1.0, "medium": 118.0},
            "notes": "Example: 1 medium banana ≈ 118 g.",
        },
        {
            "id": "chicken_breast_cooked",
            "name": "Chicken breast, cooked",
            "kcal_per_g": 1.65,
            "default_unit": "g",
            "units": {"g": 1.0},
            "notes": "",
        },
        {
            "id": "white_rice_cooked",
            "name": "White rice, cooked",
            "kcal_per_g": 1.30,
            "default_unit": "g",
            "units": {"g": 1.0, "cup": 158.0},
            "notes": "Example: 1 cup cooked white rice ≈ 158 g.",
        },
        {
            "id": "olive_oil",
            "name": "Olive oil",
            "kcal_per_g": 8.84,
            "default_unit": "g",
            "units": {"g": 1.0, "tbsp": 13.5},
            "notes": "Example: 1 tablespoon ≈ 13.5 g.",
        },
        {
            "id": "egg_large",
            "name": "Egg, large",
            "kcal_per_g": 1.43,
            "default_unit": "g",
            "units": {"g": 1.0, "egg": 50.0},
            "notes": "Example: 1 large egg ≈ 50 g.",
        },
        {
            "id": "cucumber_raw",
            "name": "Cucumber, raw",
            "kcal_per_g": 0.10,
            "default_unit": "g",
            "units": {"g": 1.0},
            "notes": "",
        },
    ],
}


def clone_default_foods() -> Dict[str, Any]:
    """Return a deep copy of the starter food-calculator database."""
    return json.loads(json.dumps(DEFAULT_FOODS))


def clone_default_recipes() -> Dict[str, Any]:
    """Return a deep copy of the starter recipe data without importing copy."""
    return json.loads(json.dumps(DEFAULT_RECIPES))


def get_app_dir() -> Path:
    """
    Portable-data rule:
    - running as .py: data lives next to this .py
    - running as .exe: data lives next to the .exe
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def get_resource_path(filename: str) -> Path:
    """
    Works as .py and as PyInstaller .exe.
    Avoids Pylance warning about sys._MEIPASS.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / filename

    return get_app_dir() / filename


def get_health_data_dir() -> Path:
    """Return the app-specific DATA folder used for all user-editable external files."""
    return get_app_dir() / DATA_DIR_NAME / HEALTH_DATA_DIR_NAME


def find_data_or_resource_file(filename: str) -> Path:
    """
    Prefer user-editable external files in DATA/HealthTracker.

    This keeps runtime assets like beep.wav out of the app/exe folder:

        DATA/HealthTracker/beep.wav

    For compatibility, old beside-the-app placement and PyInstaller bundled
    resources are still accepted as fallbacks, but new files should live in
    DATA/HealthTracker. If the file is missing, the returned path points to
    the preferred DATA/HealthTracker location so error/help text is clear.
    """
    health_data_side = get_health_data_dir() / filename
    if health_data_side.exists():
        return health_data_side

    legacy_app_side = get_app_dir() / filename
    if legacy_app_side.exists():
        return legacy_app_side

    bundled = get_resource_path(filename)
    if bundled.exists():
        return bundled

    return health_data_side


def apply_app_icon(app_or_window) -> None:
    # Prefer a replaceable icon in DATA/HealthTracker, but still support the
    # old/bundled locations so existing EXE builds keep working.
    icon_path = find_data_or_resource_file(APP_ICON_FILE)
    if icon_path.exists():
        app_or_window.setWindowIcon(QIcon(str(icon_path)))


def make_beep_sound(parent) -> Optional["QSoundEffect"]:
    """Shared workout-timer beep loader.

    Returns a QSoundEffect for DATA/HealthTracker/beep.wav, or None when the
    file or QtMultimedia is unavailable so callers fall back to
    QApplication.beep().
    """
    if QSoundEffect is None:
        return None
    beep_path = find_data_or_resource_file(BEEP_SOUND_FILE)
    if not beep_path.exists():
        return None
    try:
        sound = QSoundEffect(parent)
        sound.setSource(QUrl.fromLocalFile(str(beep_path)))
        sound.setVolume(0.65)
        return sound
    except Exception:
        return None


def play_beep(sound: Optional["QSoundEffect"]) -> None:
    try:
        if sound is not None:
            sound.play()
            return
        QApplication.beep()
    except Exception:
        pass


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(stringify_value(item) for item in value if stringify_value(item))
    if isinstance(value, dict):
        if "value" in value:
            raw_value = stringify_value(value.get("value"))
            unit = stringify_value(value.get("unit"))
            return f"{raw_value} {unit}".strip()
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def first_present(mapping: dict, *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping.get(key)
    return None


def first_nonempty_string(*values: Any) -> str:
    for value in values:
        text = stringify_value(value)
        if text:
            return text
    return ""


def calculate_number_expression(value: Any) -> Optional[float]:
    """
    Safely evaluate tiny calculator-style numeric expressions for kcal fields.

    Supported:
      120
      120+33
      120 - 33
      120*2
      120/2
      (120+33)/2

    Nothing except numbers, decimal separators, spaces, parentheses, and
    arithmetic operators is accepted. This avoids using Python eval().
    """
    text = stringify_value(value).strip()
    if not text:
        return None

    # Turkish/European decimal comma support for values like 12,5.
    text = text.replace(",", ".")

    # Convenience aliases in case the user types x or × for multiplication.
    text = text.replace("×", "*").replace("x", "*").replace("X", "*")

    if len(text) > 80:
        return None
    if not re.fullmatch(r"[0-9+\-*/().\s]+", text):
        return None

    try:
        tree = ast.parse(text, mode="eval")
    except Exception:
        return None

    def eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        # Python <3.8 compatibility shape; harmless on 3.12.
        if isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return float(node.n)  # type: ignore[attr-defined]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value_num = eval_node(node.operand)
            return value_num if isinstance(node.op, ast.UAdd) else -value_num
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ZeroDivisionError("division by zero")
            return left / right
        raise ValueError("Unsupported expression")

    try:
        result = eval_node(tree)
    except Exception:
        return None

    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def parse_float(value: Any, default: float = 0.0) -> float:
    """
    Small UI-safe float/calculator parser.

    Accepts normal numbers plus tiny arithmetic expressions such as:
      120+33
      200-45
      56*2
      (120+33)/2

    Returns default for invalid input instead of crashing the tracker.
    """
    text = stringify_value(value).replace(",", ".").strip()
    if not text:
        return default
    try:
        return float(text)
    except Exception:
        calculated = calculate_number_expression(text)
        return calculated if calculated is not None else default


def format_number(value: Any, decimals: int = 2) -> str:
    number = parse_float(value, 0.0)
    text = f"{number:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


STEP_CALORIE_COEFFICIENT = 0.0004


def parse_steps(value: Any) -> float:
    """Parse a step-count field without treating thousands commas as decimals."""
    text = stringify_value(value).strip().replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." not in text:
        text = text.replace(",", "")
    return parse_float(text, 0.0)


def format_deficit_or_surplus(value: Any) -> str:
    """Readable energy-balance text. Positive means estimated deficit; negative means estimated surplus."""
    deficit = parse_float(value, 0.0)
    rounded = round(deficit)
    if rounded >= 0:
        return f"est. deficit {rounded:.0f} kcal"
    return f"est. surplus {abs(rounded):.0f} kcal"


# -----------------------------
# Diet item snapshot helpers
# -----------------------------
def diet_item_snapshot(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store the diet item values that were visible when a day was saved.

    This prevents old diet history from being recalculated with a newer
    diet_config.json after the user's diet plan changes.
    """
    snapshot = {
        "id": stringify_value(item.get("id", "")),
        "name": stringify_value(item.get("name", item.get("id", ""))),
        "amount": item.get("amount", 0),
        "unit": stringify_value(item.get("unit", "")),
        "calories": parse_float(item.get("calories", 0), 0.0),
        "category": stringify_value(item.get("category", "Other")) or "Other",
    }

    # Optional display-only fields. These do not affect calories or saved IDs;
    # they only let split checklist entries stay visually clean, e.g. two
    # identical supplement checkboxes without showing "tablet 1/tablet 2" style labels.
    display_label = stringify_value(item.get("display_label", ""))
    if display_label:
        snapshot["display_label"] = display_label
    if bool(item.get("hide_amount_in_checklist", False)):
        snapshot["hide_amount_in_checklist"] = True
    return snapshot


def diet_items_snapshot(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [diet_item_snapshot(item) for item in items if isinstance(item, dict) and stringify_value(item.get("id", ""))]


def diet_item_checklist_label(item: Dict[str, Any]) -> str:
    """Human-friendly label for the diet checklist UI/exports.

    Internal IDs remain unique; this only controls visible text. If
    hide_amount_in_checklist is true, the UI shows only the display/name.
    """
    label = stringify_value(item.get("display_label", "")) or stringify_value(item.get("name", item.get("id", "")))
    if bool(item.get("hide_amount_in_checklist", False)):
        return label

    amount = item.get("amount", "")
    unit = stringify_value(item.get("unit", ""))
    if stringify_value(amount) == "" and not unit:
        return label

    try:
        amount_text = f"{float(amount):g}"
    except Exception:
        amount_text = stringify_value(amount)

    suffix = f"{amount_text} {unit}".strip()
    return f"{label} — {suffix}" if suffix else label


def diet_config_for_log(store: Any, date_text: str) -> Dict[str, Any]:
    """Return the config/template that belongs to a saved diet log.

    Saved logs may carry only diet_template_name before they have a frozen
    target/expenditure snapshot. For those logs, exports and history must use
    the selected template config, not always the top-level diet_config.json.
    """
    base = store.get_diet_config()
    log = store.data.get("diet", {}).get("logs", {}).get(date_text, {})
    template_name = stringify_value(log.get("diet_template_name", "")) if isinstance(log, dict) else ""
    if template_name and hasattr(store, "diet_config_for_template"):
        try:
            return store.diet_config_for_template(template_name)
        except Exception:
            return base
    return base


def diet_log_items(store: Any, date_text: str, force_current_config: bool = False) -> List[Dict[str, Any]]:
    """Return the item list that should be used for a diet date.

    Priority:
      1. Saved per-date item snapshot, if present.
      2. Current diet_config.json items for blank/new days.
      3. For old unsnapped logs, only show IDs that actually existed in that
         log instead of injecting brand-new config items into old dates.

    The correct long-term fix is still per-day snapshots. The ID-match fallback
    is only a damage-control path for legacy logs that were saved before V3.4.
    """
    log = store.data.get("diet", {}).get("logs", {}).get(date_text, {})
    config = diet_config_for_log(store, date_text) if isinstance(log, dict) and stringify_value(log.get("diet_template_name", "")) else store.get_diet_config()
    current_items = diet_items_snapshot(config.get("items", []))

    if not force_current_config:
        if isinstance(log, dict):
            snapshot = log.get("items_snapshot") or log.get("item_snapshots")
            if isinstance(snapshot, list) and snapshot:
                return diet_items_snapshot([item for item in snapshot if isinstance(item, dict)])

            checked = log.get("checked", {})
            if isinstance(checked, dict) and checked:
                checked_ids = {stringify_value(item_id) for item_id in checked.keys() if stringify_value(item_id)}
                matched_items = [item for item in current_items if stringify_value(item.get("id")) in checked_ids]
                if matched_items:
                    return matched_items

    return current_items


def diet_target_for_log(store: Any, date_text: str) -> float:
    log = store.data.get("diet", {}).get("logs", {}).get(date_text, {})
    config = diet_config_for_log(store, date_text)
    if isinstance(log, dict) and "target_calories_snapshot" in log:
        return parse_float(log.get("target_calories_snapshot"), 0.0)
    return parse_float(config.get("target_calories", 0), 0.0)


def diet_expenditure_for_log(store: Any, date_text: str) -> float:
    log = store.data.get("diet", {}).get("logs", {}).get(date_text, {})
    config = diet_config_for_log(store, date_text)
    if isinstance(log, dict) and "estimated_expenditure_snapshot" in log:
        return parse_float(log.get("estimated_expenditure_snapshot"), 0.0)
    return parse_float(config.get("estimated_expenditure", 0), 0.0)


def diet_snapshot_status(store: Any, date_text: str) -> str:
    log = store.data.get("diet", {}).get("logs", {}).get(date_text, {})
    if isinstance(log, dict) and isinstance(log.get("items_snapshot"), list) and log.get("items_snapshot"):
        return "frozen"
    return "live config fallback"


def short_diet_template_label(name: Any) -> str:
    """Compact label for the weekly overview: strips a leading 'YYYY MM DD'
    from a saved diet_template_name, leaving just the descriptive part.

    E.g. '2026 05 23 IronMeatDay' → 'IronMeatDay'. The date column header
    already shows the day, so repeating it inside the cell wastes space.
    Falls back to the full name when there's nothing descriptive after the date.
    """
    text = stringify_value(name)
    if not text:
        return ""
    match = re.match(r"^\d{4}[\s\-_/]\d{2}[\s\-_/]\d{2}\s*(.*)$", text)
    if match:
        rest = match.group(1).strip()
        return rest if rest else text
    return text


def compute_diet_energy(
    plan_total: float,
    checklist_consumed: float,
    additional_calories: float,
    additional_deficit: float,
    target: float,
    expenditure: float,
) -> Dict[str, Any]:
    """Single source of truth for the diet calorie/deficit math.

    The Diet Checklist, Diet History, and Daily Overview all call this so they
    can never disagree on the formula. This is ONLY arithmetic — which items,
    target, and expenditure apply to a given day is still resolved by the
    diet_*_for_log / diet_log_items helpers, so saved days keep their frozen
    per-day snapshots (the thing that historically broke when diets changed).
    """
    consumed = checklist_consumed + additional_calories
    # additional_deficit is treated as a calorie-offset/burn adjustment.
    adjusted_consumed = max(consumed - additional_deficit, 0.0)
    deficit_value = (expenditure - adjusted_consumed) if expenditure else additional_deficit
    return {
        "checklist_consumed": checklist_consumed,
        "additional_calories": additional_calories,
        "additional_deficit": additional_deficit,
        "consumed": consumed,
        "adjusted_consumed": adjusted_consumed,
        "missing": max(plan_total - checklist_consumed, 0.0),
        "remaining": max(target - adjusted_consumed, 0.0),
        "over": max(adjusted_consumed - target, 0.0),
        # Raw signed balance (>0 deficit, <0 surplus) kept for the History /
        # PDF / Overview code that already uses it — unchanged on purpose.
        # The Diet summary + phone use the split, never-negative pair below.
        "deficit": deficit_value,
        "deficit_pos": max(deficit_value, 0.0),
        "surplus": max(-deficit_value, 0.0),
        "plan_total": plan_total,
    }


# -----------------------------
# PDF export helpers (V3.0)
# -----------------------------
def html_escape_text(value: Any) -> str:
    return html.escape(stringify_value(value), quote=True)


def html_multiline(value: Any) -> str:
    text = html_escape_text(value)
    return text.replace("\n", "<br>") if text else ""


def compact_pdf_text(value: Any, max_chars: int = 180) -> str:
    """
    Compact PDF-only text. Markdown exports keep the full text.

    QTextDocument can split long blocks/tables over pages very easily, so PDF
    notes are intentionally shortened to keep one diet/workout entry on one A4
    portrait page whenever the source data is reasonably sized.
    """
    text = stringify_value(value).strip()
    if not text:
        return ""

    # Collapse multi-line notes into one compact line to save vertical space.
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_chars:
        text = text[: max(0, max_chars - 1)].rstrip() + "…"
    return html_escape_text(text)


def safe_filename_part(value: Any, fallback: str = "export") -> str:
    text = stringify_value(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def is_iso_date_text(value: Any) -> bool:
    text = stringify_value(value)
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except Exception:
        return False


def sorted_iso_dates(date_texts: List[str]) -> List[str]:
    return sorted({d for d in date_texts if is_iso_date_text(d)})


def last_n_iso_dates(date_texts: List[str], n: int) -> List[str]:
    dates = sorted_iso_dates(date_texts)
    return dates[-n:] if n > 0 else dates


def dates_in_range(date_texts: List[str], start_date: str, end_date: str) -> List[str]:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return [d for d in sorted_iso_dates(date_texts) if start_date <= d <= end_date]


def ask_iso_date_range(parent: QWidget, title: str, available_dates: List[str]) -> Optional[List[str]]:
    dates = sorted_iso_dates(available_dates)
    if not dates:
        QMessageBox.information(parent, APP_TITLE, "No dates available for this PDF export.")
        return None

    default_text = f"{dates[0]} to {dates[-1]}"
    text, ok = QInputDialog.getText(
        parent,
        title,
        "Enter date range as YYYY-MM-DD to YYYY-MM-DD:",
        text=default_text,
    )
    if not ok:
        return None

    found_dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    if len(found_dates) < 2:
        QMessageBox.warning(parent, APP_TITLE, "Please enter two dates, for example: 2026-04-01 to 2026-04-29")
        return None

    start_date, end_date = found_dates[0], found_dates[1]
    if not is_iso_date_text(start_date) or not is_iso_date_text(end_date):
        QMessageBox.warning(parent, APP_TITLE, "Date format must be YYYY-MM-DD.")
        return None

    selected_dates = dates_in_range(dates, start_date, end_date)
    if not selected_dates:
        QMessageBox.information(parent, APP_TITLE, f"No records found between {start_date} and {end_date}.")
        return None
    return selected_dates


def health_report_default_path(store: "UnifiedStore", suffix: str, ext: str = "pdf") -> Path:
    exports_dir = getattr(store, "exports_dir", None)
    if exports_dir is None:
        exports_dir = store.data_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return exports_dir / f"{suffix}_{stamp}.{ext.lstrip('.')}"


def readable_export_date_stamp() -> str:
    return datetime.now().strftime("%d-%m-%Y")


def health_report_named_path(store: "UnifiedStore", base_name: str, ext: str = "pdf") -> Path:
    """Return a readable default export path in DATA/HealthTracker/exports.

    Example: AllDietHistory_05-05-2026.md
    """
    exports_dir = getattr(store, "exports_dir", None)
    if exports_dir is None:
        exports_dir = store.data_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    cleaned = stringify_value(base_name).strip() or "HealthTrackerExport"
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_") or "HealthTrackerExport"
    return exports_dir / f"{cleaned}_{readable_export_date_stamp()}.{ext.lstrip('.')}"


def health_report_html(title: str, subtitle: str, body_html: str) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 7.1pt;
    line-height: 1.08;
    color: #222;
}}
h1 {{
    font-size: 13.5pt;
    margin: 0 0 2px 0;
}}
h2 {{
    font-size: 10pt;
    margin: 4px 0 3px 0;
}}
h3 {{
    font-size: 8.2pt;
    margin: 4px 0 2px 0;
}}
p {{
    margin: 2px 0 3px 0;
}}
.meta {{
    color: #555;
    font-size: 6.7pt;
    line-height: 1.05;
    margin-bottom: 4px;
}}
.small {{
    color: #666;
    font-size: 6.7pt;
    line-height: 1.05;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 2px 0 5px 0;
}}
th, td {{
    border: 1px solid #b8b8b8;
    padding: 1.4px 2px;
    vertical-align: top;
}}
th {{
    background: #f2f2f2;
    font-weight: bold;
}}
.compact th,
.compact td {{
    padding: 1px 1.6px;
}}
.metrics th,
.metrics td {{
    text-align: center;
    padding: 1.3px 1.6px;
}}
.diet-checklist th,
.diet-checklist td {{
    font-size: 6.6pt;
    padding: 0.8px 1.4px;
}}
.workout-table th,
.workout-table td {{
    font-size: 6.45pt;
    padding: 0.7px 1.2px;
}}
.num {{
    text-align: right;
    white-space: nowrap;
}}
.center {{
    text-align: center;
}}
.note {{
    border: 1px solid #d0d0d0;
    background: #fafafa;
    padding: 2px;
    margin: 1px 0 3px 0;
    font-size: 6.5pt;
    line-height: 1.03;
}}
.truncated {{
    color: #777;
    font-size: 6.2pt;
}}
.page-break {{
    page-break-before: always;
    break-before: page;
    display: block;
    height: 0;
    margin: 0;
    padding: 0;
}}
</style>
</head>
<body>
<h1>{html_escape_text(title)}</h1>
<div class="meta">
<b>Generated:</b> {html_escape_text(generated_at)}<br>
{html_multiline(subtitle)}
</div>
{body_html}
</body>
</html>
"""


def export_html_pdf(path: Path, title: str, subtitle: str, body_html: str, landscape: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait)
    printer.setPageMargins(QMarginsF(6, 6, 6, 6), QPageLayout.Unit.Millimeter)

    doc = QTextDocument()
    doc.setDefaultFont(QFont("Arial", 7))
    doc.setHtml(health_report_html(title, subtitle, body_html))
    try:
        doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
    except Exception:
        pass
    doc.print(printer)



# -----------------------------
# Workout template normalization
# -----------------------------
BASIC_EXERCISE_KEYS = {
    "name", "exercise", "title", "movement", "label",
    "sets_reps", "setsReps", "sets_x_reps", "setsXReps", "scheme", "prescription",
    "sets", "set_count", "setCount", "reps", "rep_count", "repCount", "rep_range", "repRange",
    "target_load", "targetLoad", "load", "weight", "target", "intensity",
    "notes", "note", "instructions", "instruction", "cue", "cues", "tips",
}


class ExerciseDef:
    def __init__(self, name: str, sets_reps: str = "", target_load: str = "", notes: str = "", extra: Optional[Dict[str, Any]] = None):
        self.name = name
        self.sets_reps = sets_reps
        self.target_load = target_load
        self.notes = notes
        # V4.0: Preserve unknown/template-specific fields such as:
        # type, steps, rounds, step_seconds, rest_seconds, between_round_rest_seconds.
        # This is important so manual JSON edits do not get stripped later.
        self.extra: Dict[str, Any] = dict(extra or {})

    def template_dict(self) -> Dict[str, Any]:
        data = dict(self.extra)
        # History-only fields should not leak into workout_templates.json if templates
        # are serialized after import/edit.
        data.pop("done", None)
        data.pop("rir", None)
        data["name"] = self.name
        data["sets_reps"] = self.sets_reps
        data["target_load"] = self.target_load
        data["notes"] = self.notes
        return data

    def field(self, *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in self.extra and self.extra.get(key) not in (None, ""):
                return self.extra.get(key)
        return default

    def exercise_type(self) -> str:
        return stringify_value(self.field("type", "kind", "mode", default="")).lower()


class WorkoutTemplate:
    def __init__(self, name: str, exercises: Optional[List[ExerciseDef]] = None, warmup_notes: str = "", extra: Optional[Dict[str, Any]] = None):
        self.name = name
        self.exercises = exercises or []
        self.warmup_notes = warmup_notes
        self.extra: Dict[str, Any] = dict(extra or {})

    def default_rest_seconds(self) -> int:
        return parse_positive_int(
            first_present(self.extra, "_default_rest_seconds", "default_rest_seconds", "rest_seconds"),
            75,
        )


def parse_positive_int(value: Any, default: int = 0) -> int:
    text = stringify_value(value).strip()
    if not text:
        return default
    try:
        number = int(float(text.replace(",", ".")))
        return number if number >= 0 else default
    except Exception:
        return default


def parse_sets_count(text: Any, default: int = 1) -> int:
    s = stringify_value(text).lower().replace("×", "x")
    # Examples: "2 x 11", "3 x 30 seconds", "3 sets"
    m = re.search(r"\b(\d+)\s*x\s*\d+", s)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"\b(\d+)\s*(?:sets?|rounds?)\b", s)
    if m:
        return max(1, int(m.group(1)))
    return default


def parse_seconds_from_text(text: Any, default: int = 0) -> int:
    s = stringify_value(text).lower().replace("×", "x")
    # Examples: "3 x 30 seconds", "30 sec", "45s"
    m = re.search(r"x\s*(\d+)\s*(?:seconds?|secs?|s)\b", s)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"\b(\d+)\s*(?:seconds?|secs?|s)\b", s)
    if m:
        return max(1, int(m.group(1)))
    return default


def normalize_warmup_notes(template_data: dict) -> str:
    return stringify_value(
        first_present(
            template_data,
            "_warmup_notes",
            "warmup_notes",
            "warmupNotes",
            "warmup_note",
            "warmupNote",
            "warmup",
            "warm_up",
        )
    )


def normalize_sets_reps(exercise_data: dict) -> str:
    direct_value = first_present(
        exercise_data,
        "sets_reps",
        "setsReps",
        "sets_x_reps",
        "setsXReps",
        "scheme",
        "prescription",
    )
    if direct_value is not None:
        return stringify_value(direct_value)

    sets_value = first_present(exercise_data, "sets", "set_count", "setCount")
    reps_value = first_present(exercise_data, "reps", "rep_count", "repCount", "rep_range", "repRange")
    if sets_value is None and reps_value is None:
        return ""
    if sets_value is None:
        return stringify_value(reps_value)
    if reps_value is None:
        return stringify_value(sets_value)
    return f"{stringify_value(sets_value)} × {stringify_value(reps_value)}"


def normalize_target_load(exercise_data: dict) -> str:
    return stringify_value(first_present(exercise_data, "target_load", "targetLoad", "load", "weight", "target", "intensity"))


def normalize_exercise_notes(exercise_data: dict) -> str:
    return stringify_value(first_present(exercise_data, "notes", "note", "instructions", "instruction", "cue", "cues", "tips"))


def normalize_exercise_definition(exercise_data: Any, fallback_name: str = "") -> ExerciseDef:
    if isinstance(exercise_data, str):
        name = exercise_data.strip() or fallback_name
        if not name:
            raise ValueError("Exercise entry is missing a name.")
        return ExerciseDef(name, "", "", "", extra={})

    if not isinstance(exercise_data, dict):
        raise ValueError(f"Unsupported exercise entry type: {type(exercise_data).__name__}")

    name = stringify_value(first_present(exercise_data, "name", "exercise", "title", "movement", "label")) or fallback_name
    if not name:
        if stringify_value(exercise_data.get("type")).lower() == "hiit":
            name = "HIIT Block"
        else:
            raise ValueError(f"Exercise entry is missing a name: {exercise_data}")

    return ExerciseDef(
        name=name,
        sets_reps=normalize_sets_reps(exercise_data),
        target_load=normalize_target_load(exercise_data),
        notes=normalize_exercise_notes(exercise_data),
        extra=dict(exercise_data),
    )


def looks_like_exercise_list(items: list) -> bool:
    if not items:
        return True
    for item in items:
        if isinstance(item, str):
            continue
        if isinstance(item, dict) and (
            first_present(item, "name", "exercise", "title", "movement", "label")
            or stringify_value(item.get("type")).lower() == "hiit"
        ):
            continue
        return False
    return True


def split_template_list_items(items: list) -> Tuple[list, str]:
    exercise_items: List[Any] = []
    warmup_notes = ""

    for item in items:
        if isinstance(item, dict):
            maybe_warmup = normalize_warmup_notes(item)
            has_exercise_name = first_present(item, "name", "exercise", "title", "movement", "label")
            if maybe_warmup and not has_exercise_name and stringify_value(item.get("type")).lower() != "hiit":
                if not warmup_notes:
                    warmup_notes = maybe_warmup
                continue
        exercise_items.append(item)

    return exercise_items, warmup_notes


def template_payload_from_dict(template_name: str, template_value: dict, shared_warmup_notes: str = "") -> Dict[str, Any]:
    exercises = first_present(template_value, "exercises", "items", "movements", "exercise_list", "exerciseList")
    nested_name = stringify_value(
        first_present(template_value, "name", "template", "title", "workout_name", "workoutName")
    ) or str(template_name)
    payload = dict(template_value)
    payload["name"] = nested_name
    payload["exercises"] = exercises if isinstance(exercises, list) else []
    payload["warmup_notes"] = first_nonempty_string(normalize_warmup_notes(template_value), shared_warmup_notes)
    return payload


def extract_template_payloads(raw_data: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(raw_data, dict):
        if not raw_data:
            return {}

        shared_warmup_notes = normalize_warmup_notes(raw_data)
        container_value = first_present(raw_data, "templates", "workouts", "routines", "programs", "days")
        if container_value is not None:
            extracted = extract_template_payloads(container_value)
            if shared_warmup_notes:
                for payload in extracted.values():
                    payload["warmup_notes"] = first_nonempty_string(payload.get("warmup_notes", ""), shared_warmup_notes)
            return extracted

        extracted_from_nested: Dict[str, Dict[str, Any]] = {}
        for template_name, template_value in raw_data.items():
            if str(template_name).startswith("_"):
                continue

            if isinstance(template_value, list):
                exercise_items, warmup_notes = split_template_list_items(template_value)
                if looks_like_exercise_list(exercise_items):
                    extracted_from_nested[str(template_name)] = {
                        "name": str(template_name),
                        "exercises": exercise_items,
                        "warmup_notes": first_nonempty_string(warmup_notes, shared_warmup_notes),
                    }
                    continue

            if isinstance(template_value, dict):
                exercises = first_present(template_value, "exercises", "items", "movements", "exercise_list", "exerciseList")
                if isinstance(exercises, list):
                    extracted_from_nested[str(template_name)] = template_payload_from_dict(str(template_name), template_value, shared_warmup_notes)

        if extracted_from_nested:
            return extracted_from_nested

        exercises = first_present(raw_data, "exercises", "items", "movements", "exercise_list", "exerciseList")
        single_name = stringify_value(first_present(raw_data, "name", "template", "title", "workout_name", "workoutName"))
        if single_name and isinstance(exercises, list):
            return {single_name: template_payload_from_dict(single_name, raw_data)}

        raise ValueError("Template JSON format was not recognized.")

    if isinstance(raw_data, list):
        exercise_items, warmup_notes = split_template_list_items(raw_data)
        if looks_like_exercise_list(exercise_items):
            return {"Imported Template": {"name": "Imported Template", "exercises": exercise_items, "warmup_notes": warmup_notes}}

        templates: Dict[str, Dict[str, Any]] = {}
        for index, item in enumerate(raw_data, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Template item #{index} must be an object, got {type(item).__name__}.")
            template_name = stringify_value(first_present(item, "name", "template", "title", "workout_name", "workoutName")) or f"Template {index}"
            exercises = first_present(item, "exercises", "items", "movements", "exercise_list", "exerciseList")
            if not isinstance(exercises, list):
                raise ValueError(f"Template '{template_name}' is missing an exercises list.")
            templates[template_name] = template_payload_from_dict(template_name, item)
        return templates

    raise ValueError(f"Top-level JSON must be an object or a list, got {type(raw_data).__name__}.")


def build_templates(template_data: Any) -> Dict[str, WorkoutTemplate]:
    raw_templates = extract_template_payloads(template_data)
    templates: Dict[str, WorkoutTemplate] = {}

    for template_name, payload in raw_templates.items():
        normalized_name = str(template_name).strip()
        if not normalized_name:
            continue

        raw_exercises = payload.get("exercises", [])
        normalized_exercises: List[ExerciseDef] = []
        for index, exercise in enumerate(raw_exercises, start=1):
            normalized_exercises.append(normalize_exercise_definition(exercise, fallback_name=f"Exercise {index}"))

        extra = dict(payload)
        extra.pop("exercises", None)
        extra.pop("name", None)
        templates[normalized_name] = WorkoutTemplate(
            name=normalized_name,
            exercises=normalized_exercises,
            warmup_notes=stringify_value(payload.get("warmup_notes", "")),
            extra=extra,
        )

    return templates


def serialize_templates(templates: Dict[str, WorkoutTemplate]) -> Dict[str, dict]:
    data: Dict[str, dict] = {}
    for template_name, template in templates.items():
        payload = dict(template.extra)
        payload["_warmup_notes"] = template.warmup_notes
        payload["exercises"] = [exercise.template_dict() for exercise in template.exercises]
        data[template_name] = payload
    return data


def deserialize_templates(data: Dict[str, Any]) -> Dict[str, WorkoutTemplate]:
    if not data:
        return {}
    return build_templates(data)


# -----------------------------
# Split-file store
# -----------------------------
class UnifiedStore:
    """
    V1.2 storage model.

    The app still uses one in-memory structure for convenience:

        self.data["diet"]["config"]
        self.data["diet"]["logs"]
        self.data["workout"]["templates"]
        self.data["workout"]["history"]
        self.data["workout"]["settings"]
        self.data["recipes"]["recipes"]

    But it saves to separate JSON files:

        DATA/HealthTracker/DietTracker/diet_config.json
        DATA/HealthTracker/DietTracker/diet_logs.json
        DATA/HealthTracker/WorkoutTracker/workout_templates.json
        DATA/HealthTracker/WorkoutTracker/workout_history.json
        DATA/HealthTracker/recipes.json

    This gives you editable separation without making the UI code fragile.
    """

    def __init__(self, app_dir: Path):
        self.app_dir = app_dir

        # V2.5 portable nested storage layout:
        #
        #   DATA\HealthTracker\recipes.json
        #   DATA\HealthTracker\DietTracker\diet_config.json
        #   DATA\HealthTracker\DietTracker\diet_logs.json
        #   DATA\HealthTracker\WorkoutTracker\workout_templates.json
        #   DATA\HealthTracker\WorkoutTracker\workout_history.json
        #
        # Older versions saved these JSON files directly under DATA.  V2.5
        # still searches that old location and migrates it into this layout.
        self.root_data_dir = self.app_dir / DATA_DIR_NAME
        self.data_dir = self.root_data_dir / HEALTH_DATA_DIR_NAME
        self.diet_data_dir = self.data_dir / DIET_DATA_DIR_NAME
        self.workout_data_dir = self.data_dir / WORKOUT_DATA_DIR_NAME

        self.root_data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.diet_data_dir.mkdir(parents=True, exist_ok=True)
        self.workout_data_dir.mkdir(parents=True, exist_ok=True)
        self.diet_templates_dir = self.diet_data_dir / DIET_CONFIG_TEMPLATES_DIR_NAME
        self.diet_templates_dir.mkdir(parents=True, exist_ok=True)

        self.diet_config_path = self.diet_data_dir / DIET_CONFIG_FILE
        self.diet_template_settings_path = self.diet_data_dir / DIET_TEMPLATE_SETTINGS_FILE
        self.diet_logs_path = self.diet_data_dir / DIET_LOGS_FILE
        self.workout_templates_path = self.workout_data_dir / WORKOUT_TEMPLATES_FILE
        self.workout_history_path = self.workout_data_dir / WORKOUT_HISTORY_FILE
        self.recipes_path = self.data_dir / RECIPES_FILE
        self.foods_path = self.data_dir / FOODS_FILE

        self.backup_dir = self.data_dir / "backups"
        self.exports_dir = self.data_dir / "exports"
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        self.data = self.default_data()
        self.import_messages: List[str] = []
        self.load_or_create()

    def default_data(self) -> Dict[str, Any]:
        return {
            "schema_version": 2,
            "app": {
                "name": APP_TITLE,
                "version_created": APP_VERSION,
                "last_saved_at": "",
                "storage_model": "split_json_v2_nested",
            },
            "diet": {
                "config": DEFAULT_DIET_CONFIG,
                "logs": {},
            },
            "workout": {
                "templates": {},
                "history": [],
                "settings": {"last_selected_template": ""},
            },
            "recipes": clone_default_recipes(),
            "foods": clone_default_foods(),
        }

    def backup_file(self, path: Path) -> Optional[Path]:
        if not path.exists():
            return None
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.backup_dir / f"{path.stem}.backup_{stamp}{path.suffix}"
        shutil.copy2(path, backup)
        return backup

    def split_files_exist(self) -> bool:
        return (
            self.diet_config_path.exists()
            or self.diet_logs_path.exists()
            or self.diet_template_settings_path.exists()
            or any(self.diet_data_dir.glob("diet_config_*.json"))
            or any(self.diet_data_dir.glob("diet-config-*.json"))
            or any(self.diet_templates_dir.glob("*.json"))
            or self.workout_templates_path.exists()
            or self.workout_history_path.exists()
            or self.recipes_path.exists()
            or self.foods_path.exists()
        )

    def load_or_create(self) -> None:
        # Split JSON files are the only storage model. If none exist yet (fresh
        # install or a deliberately deleted DATA folder), start a clean store.
        if self.split_files_exist():
            self.load_split_files()
            return

        self.data = self.default_data()
        self.save()

    def load_split_files(self) -> None:
        self.data = self.default_data()

        # Diet config.
        if self.diet_config_path.exists():
            try:
                loaded = read_json(self.diet_config_path)
                if isinstance(loaded, dict):
                    self.data["diet"]["config"] = self.normalize_diet_config(loaded)
                else:
                    raise ValueError("diet_config.json must contain a JSON object.")
            except Exception as exc:
                self.backup_file(self.diet_config_path)
                self.import_messages.append(f"Could not read diet_config.json; using defaults. Error: {exc}")

        # Diet logs.
        if self.diet_logs_path.exists():
            try:
                loaded = read_json(self.diet_logs_path)
                if isinstance(loaded, dict):
                    self.data["diet"]["logs"] = loaded
                    self.migrate_diet_log_ids(self.data)
                else:
                    raise ValueError("diet_logs.json must contain a JSON object.")
            except Exception as exc:
                self.backup_file(self.diet_logs_path)
                self.import_messages.append(f"Could not read diet_logs.json; using empty logs. Error: {exc}")

        # Workout templates.
        if self.workout_templates_path.exists():
            try:
                loaded = read_json(self.workout_templates_path)
                if isinstance(loaded, dict):
                    # Validate by attempting to deserialize.
                    _ = deserialize_templates(loaded)
                    self.data["workout"]["templates"] = loaded
                else:
                    raise ValueError("workout_templates.json must contain a JSON object.")
            except Exception as exc:
                self.backup_file(self.workout_templates_path)
                self.import_messages.append(f"Could not read workout_templates.json; using empty templates. Error: {exc}")

        # Workout history/settings.
        if self.workout_history_path.exists():
            try:
                loaded = read_json(self.workout_history_path)

                if isinstance(loaded, list):
                    # Accept a simple list, but normalize into object form.
                    self.data["workout"]["history"] = loaded
                    self.data["workout"]["settings"] = {"last_selected_template": ""}
                elif isinstance(loaded, dict):
                    history = loaded.get("history", [])
                    settings = loaded.get("settings", {"last_selected_template": ""})
                    self.data["workout"]["history"] = history if isinstance(history, list) else []
                    self.data["workout"]["settings"] = settings if isinstance(settings, dict) else {"last_selected_template": ""}
                else:
                    raise ValueError("workout_history.json must contain a JSON object or list.")
            except Exception as exc:
                self.backup_file(self.workout_history_path)
                self.import_messages.append(f"Could not read workout_history.json; using empty workout history. Error: {exc}")

        # Recipes. If the file is missing, the starter recipes remain in memory and are saved below.
        if self.recipes_path.exists():
            try:
                loaded = read_json(self.recipes_path)
                self.data["recipes"] = self.normalize_recipes_data(loaded)
            except Exception as exc:
                self.backup_file(self.recipes_path)
                self.data["recipes"] = clone_default_recipes()
                self.import_messages.append(f"Could not read recipes.json; using starter recipes. Error: {exc}")

        # Foods. This powers the Food Calculator tab. Missing files get seeded below.
        if self.foods_path.exists():
            try:
                loaded = read_json(self.foods_path)
                self.data["foods"] = self.normalize_foods_data(loaded)
            except Exception as exc:
                self.backup_file(self.foods_path)
                self.data["foods"] = clone_default_foods()
                self.import_messages.append(f"Could not read foods.json; using starter foods. Error: {exc}")

        self.data = self.normalize_data(self.data)

        # Save once so missing files get created and migrated data is normalized.
        self.save()

    def normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        base = self.default_data()

        if not isinstance(data.get("diet"), dict):
            data["diet"] = base["diet"]
        if not isinstance(data["diet"].get("config"), dict):
            data["diet"]["config"] = DEFAULT_DIET_CONFIG
        if not isinstance(data["diet"].get("logs"), dict):
            data["diet"]["logs"] = {}

        if not isinstance(data.get("workout"), dict):
            data["workout"] = base["workout"]
        if not isinstance(data["workout"].get("templates"), dict):
            data["workout"]["templates"] = {}
        if not isinstance(data["workout"].get("history"), list):
            data["workout"]["history"] = []
        if not isinstance(data["workout"].get("settings"), dict):
            data["workout"]["settings"] = {"last_selected_template": ""}

        if not isinstance(data.get("recipes"), (dict, list)):
            data["recipes"] = clone_default_recipes()
        data["recipes"] = self.normalize_recipes_data(data["recipes"])

        if not isinstance(data.get("foods"), (dict, list)):
            data["foods"] = clone_default_foods()
        data["foods"] = self.normalize_foods_data(data["foods"])

        data["diet"]["config"] = self.normalize_diet_config(data["diet"]["config"])
        data.setdefault("schema_version", 2)
        data.setdefault("app", base["app"])
        data["app"]["storage_model"] = "split_json_v2_nested"

        self.migrate_diet_log_ids(data)
        return data

    def save(self) -> None:
        self.data.setdefault("app", {})["last_saved_at"] = datetime.now().isoformat(timespec="seconds")

        # V5.4: external diet templates under DietTracker/diet_configs are now
        # the preferred diet source.  Do not recreate diet_config.json when the
        # user intentionally deleted it and external configs exist.
        if self.diet_config_path.exists() or not self.external_diet_config_paths():
            write_json(self.diet_config_path, self.data["diet"].get("config", DEFAULT_DIET_CONFIG))
        write_json(self.diet_logs_path, self.data["diet"].get("logs", {}))
        write_json(self.workout_templates_path, self.data["workout"].get("templates", {}))
        write_json(
            self.workout_history_path,
            {
                "history": self.data["workout"].get("history", []),
                "settings": self.data["workout"].get("settings", {"last_selected_template": ""}),
            },
        )
        write_json(self.recipes_path, self.data.get("recipes", clone_default_recipes()))
        write_json(self.foods_path, self.data.get("foods", clone_default_foods()))

    def normalize_diet_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        config.setdefault("target_calories", DEFAULT_DIET_CONFIG["target_calories"])
        config.setdefault("estimated_expenditure", DEFAULT_DIET_CONFIG["estimated_expenditure"])
        config.setdefault("notes", "")
        config.setdefault("items", [])

        seen: Dict[str, int] = {}
        for i, item in enumerate(config["items"]):
            if not isinstance(item, dict):
                config["items"][i] = {
                    "id": f"item_{i+1}",
                    "name": f"Item {i+1}",
                    "amount": 1,
                    "unit": "",
                    "calories": 0,
                    "category": "Other",
                }
                continue

            item_id = str(item.get("id", "")).strip()
            if not item_id:
                item_id = self.safe_id(item.get("name", f"item_{i+1}"), f"item_{i+1}")
                item["id"] = item_id

            if item_id in seen:
                seen[item_id] += 1
                item["id"] = f"{item_id}_{seen[item_id]}"
            else:
                seen[item_id] = 1

            item.setdefault("name", item["id"])
            item.setdefault("amount", 1)
            item.setdefault("unit", "")
            item.setdefault("calories", 0)
            item.setdefault("category", "Other")

        return config

    def normalize_recipes_data(self, raw_data: Any) -> Dict[str, Any]:
        """
        Normal recipes file shape:

            {
              "schema_version": 1,
              "recipes": [
                {
                  "id": "custom_boiled_lentils",
                  "name": "Custom Boiled Lentils",
                  "total_amount": 320,
                  "unit": "g",
                  "total_calories": 391.02,
                  "ingredients": [
                    {"name": "Lentils, boiled", "amount": 282.42, "unit": "g", "calories": 327.61}
                  ],
                  "notes": ""
                }
              ]
            }

        A plain list of recipe objects is also accepted and normalized.
        """
        if isinstance(raw_data, list):
            recipes = raw_data
            container: Dict[str, Any] = {"schema_version": 1, "recipes": recipes}
        elif isinstance(raw_data, dict):
            container = dict(raw_data)
            recipes = first_present(container, "recipes", "items")
            if recipes is None and all(isinstance(v, dict) for v in container.values()):
                recipes = list(container.values())
            if recipes is None:
                recipes = []
            container["recipes"] = recipes
        else:
            container = clone_default_recipes()
            recipes = container["recipes"]

        if not isinstance(recipes, list):
            recipes = []

        normalized: List[dict] = []
        seen: Dict[str, int] = {}
        for index, recipe in enumerate(recipes, start=1):
            if not isinstance(recipe, dict):
                continue

            name = first_nonempty_string(recipe.get("name"), recipe.get("title"), f"Recipe {index}")
            recipe_id = first_nonempty_string(recipe.get("id"), self.safe_id(name, f"recipe_{index}"))
            if recipe_id in seen:
                seen[recipe_id] += 1
                recipe_id = f"{recipe_id}_{seen[recipe_id]}"
            else:
                seen[recipe_id] = 1

            raw_ingredients = recipe.get("ingredients", [])
            ingredients: List[dict] = []
            if isinstance(raw_ingredients, list):
                for ing_index, ingredient in enumerate(raw_ingredients, start=1):
                    if not isinstance(ingredient, dict):
                        continue
                    ing_name = first_nonempty_string(ingredient.get("name"), ingredient.get("food"), f"Ingredient {ing_index}")
                    ingredients.append(
                        {
                            "name": ing_name,
                            "amount": parse_float(first_present(ingredient, "amount", "grams", "quantity"), 0.0),
                            "unit": first_nonempty_string(ingredient.get("unit"), "g"),
                            "calories": parse_float(first_present(ingredient, "calories", "kcal", "energy"), 0.0),
                        }
                    )

            ingredient_amount_sum = sum(float(ing.get("amount", 0) or 0) for ing in ingredients)
            ingredient_calorie_sum = sum(float(ing.get("calories", 0) or 0) for ing in ingredients)

            total_amount_value = first_present(recipe, "total_amount", "amount", "grams", "quantity")
            total_calories_value = first_present(recipe, "total_calories", "calories", "kcal", "energy")

            normalized.append(
                {
                    "id": recipe_id,
                    "name": name,
                    "total_amount": parse_float(total_amount_value, ingredient_amount_sum),
                    "unit": first_nonempty_string(recipe.get("unit"), "g"),
                    "total_calories": parse_float(total_calories_value, ingredient_calorie_sum),
                    "ingredients": ingredients,
                    "notes": stringify_value(recipe.get("notes", "")),
                    "updated_at": stringify_value(recipe.get("updated_at", "")),
                }
            )

        # If no valid recipes were found at all, seed the starter recipes.
        if not normalized:
            return clone_default_recipes()

        return {"schema_version": int(parse_float(container.get("schema_version", 1), 1)), "recipes": normalized}

    def get_recipes(self) -> List[dict]:
        self.data["recipes"] = self.normalize_recipes_data(self.data.get("recipes", clone_default_recipes()))
        return self.data["recipes"].setdefault("recipes", [])

    def save_recipes_file(self) -> None:
        self.data["recipes"] = self.normalize_recipes_data(self.data.get("recipes", clone_default_recipes()))
        write_json(self.recipes_path, self.data["recipes"])

    def add_recipe(self, recipe: dict) -> None:
        recipes = self.get_recipes()
        clean_recipe = self.normalize_recipes_data([recipe])["recipes"][0]
        existing_ids = {r.get("id", "") for r in recipes}
        if clean_recipe["id"] in existing_ids:
            base_id = clean_recipe["id"]
            suffix = 2
            while f"{base_id}_{suffix}" in existing_ids:
                suffix += 1
            clean_recipe["id"] = f"{base_id}_{suffix}"
        clean_recipe["updated_at"] = datetime.now().isoformat(timespec="seconds")
        recipes.append(clean_recipe)
        self.save_recipes_file()

    def update_recipe(self, old_recipe: dict, new_recipe: dict) -> None:
        recipes = self.get_recipes()
        clean_recipe = self.normalize_recipes_data([new_recipe])["recipes"][0]
        clean_recipe["updated_at"] = datetime.now().isoformat(timespec="seconds")
        for idx, recipe in enumerate(recipes):
            if recipe is old_recipe or recipe == old_recipe or recipe.get("id") == old_recipe.get("id"):
                # Keep the original id unless the user explicitly changed the recipe name/id in the JSON later.
                clean_recipe["id"] = old_recipe.get("id", clean_recipe["id"])
                recipes[idx] = clean_recipe
                self.save_recipes_file()
                return
        raise ValueError("Recipe not found.")

    def delete_recipe(self, old_recipe: dict) -> None:
        recipes = self.get_recipes()
        for idx, recipe in enumerate(recipes):
            if recipe is old_recipe or recipe == old_recipe or recipe.get("id") == old_recipe.get("id"):
                del recipes[idx]
                self.save_recipes_file()
                return
        raise ValueError("Recipe not found.")

    def restore_starter_recipes(self) -> int:
        """Add missing starter recipes without overwriting user edits."""
        recipes = self.get_recipes()
        existing_ids = {recipe.get("id", "") for recipe in recipes}
        added = 0
        for starter in clone_default_recipes().get("recipes", []):
            if starter.get("id") not in existing_ids:
                starter["updated_at"] = datetime.now().isoformat(timespec="seconds")
                recipes.append(starter)
                existing_ids.add(starter.get("id", ""))
                added += 1
        if added:
            self.save_recipes_file()
        return added

    def normalize_foods_data(self, raw_data: Any) -> Dict[str, Any]:
        """
        Food calculator JSON shape:

            {
              "schema_version": 1,
              "global_units": {"g": 1.0},
              "foods": [
                {
                  "id": "bananas_raw",
                  "name": "Bananas, Raw",
                  "kcal_per_g": 0.88,
                  "default_unit": "g",
                  "units": {"g": 1.0, "medium banana": 118.0},
                  "notes": "Optional notes"
                }
              ]
            }

        Unit values are grams per unit. Example: "medium banana": 118 means
        2 medium banana × 118 g × kcal_per_g.
        """
        if isinstance(raw_data, list):
            container: Dict[str, Any] = {"schema_version": 1, "foods": raw_data, "global_units": {"g": 1.0}}
        elif isinstance(raw_data, dict):
            container = dict(raw_data)
            if "foods" not in container and "items" in container:
                container["foods"] = container.get("items")
            if "foods" not in container and all(isinstance(v, dict) for v in container.values()):
                # Accept a plain mapping of id -> food objects.
                container["foods"] = [dict(v, id=k) for k, v in container.items() if isinstance(v, dict)]
            container.setdefault("foods", [])
            container.setdefault("global_units", {"g": 1.0})
        else:
            container = clone_default_foods()

        global_units_raw = container.get("global_units", {})
        global_units: Dict[str, float] = {"g": 1.0}
        if isinstance(global_units_raw, dict):
            for unit_name, grams in global_units_raw.items():
                unit_text = stringify_value(unit_name)
                if not unit_text:
                    continue
                grams_value = parse_float(grams, 0.0)
                if grams_value > 0:
                    global_units[unit_text] = grams_value

        foods_raw = container.get("foods", [])
        if not isinstance(foods_raw, list):
            foods_raw = []

        normalized: List[dict] = []
        seen: Dict[str, int] = {}
        for index, raw_food in enumerate(foods_raw, start=1):
            if not isinstance(raw_food, dict):
                continue
            name = first_nonempty_string(raw_food.get("name"), raw_food.get("food"), raw_food.get("title"), f"Food {index}")
            food_id = first_nonempty_string(raw_food.get("id"), self.safe_id(name, f"food_{index}"))
            if food_id in seen:
                seen[food_id] += 1
                food_id = f"{food_id}_{seen[food_id]}"
            else:
                seen[food_id] = 1

            kcal_per_g_value = first_present(raw_food, "kcal_per_g", "calories_per_g", "calories_per_gram", "kcal_per_gram")
            kcal_per_g = parse_float(kcal_per_g_value, -1.0)
            if kcal_per_g < 0:
                kcal_100 = first_present(raw_food, "kcal_per_100g", "calories_per_100g", "kcal_100g", "calories_100g")
                kcal_per_g = parse_float(kcal_100, 0.0) / 100.0

            units: Dict[str, float] = {}
            units.update(global_units)
            raw_units = raw_food.get("units", {})
            if isinstance(raw_units, dict):
                for unit_name, grams in raw_units.items():
                    unit_text = stringify_value(unit_name)
                    if not unit_text:
                        continue
                    grams_value = parse_float(grams, 0.0)
                    if grams_value > 0:
                        units[unit_text] = grams_value
            elif isinstance(raw_units, list):
                for unit in raw_units:
                    if not isinstance(unit, dict):
                        continue
                    unit_text = first_nonempty_string(unit.get("name"), unit.get("unit"), unit.get("label"))
                    grams_value = parse_float(first_present(unit, "grams", "g", "unit_grams", "grams_per_unit"), 0.0)
                    if unit_text and grams_value > 0:
                        units[unit_text] = grams_value

            units.setdefault("g", 1.0)
            default_unit = first_nonempty_string(raw_food.get("default_unit"), raw_food.get("unit"), "g")
            if default_unit not in units:
                units[default_unit] = 1.0

            normalized.append(
                {
                    "id": food_id,
                    "name": name,
                    "kcal_per_g": kcal_per_g,
                    "default_unit": default_unit,
                    "units": units,
                    "notes": stringify_value(raw_food.get("notes", "")),
                }
            )

        if not normalized:
            return clone_default_foods()

        return {
            "schema_version": int(parse_float(container.get("schema_version", 1), 1)),
            "notes": stringify_value(container.get("notes", DEFAULT_FOODS.get("notes", ""))),
            "global_units": global_units,
            "foods": normalized,
        }

    def get_foods(self) -> List[dict]:
        self.data["foods"] = self.normalize_foods_data(self.data.get("foods", clone_default_foods()))
        return self.data["foods"].setdefault("foods", [])

    def save_foods_file(self) -> None:
        self.data["foods"] = self.normalize_foods_data(self.data.get("foods", clone_default_foods()))
        write_json(self.foods_path, self.data["foods"])

    def reload_foods_file(self) -> None:
        if self.foods_path.exists():
            self.data["foods"] = self.normalize_foods_data(read_json(self.foods_path))
        else:
            self.data["foods"] = clone_default_foods()
            self.save_foods_file()

    def safe_id(self, text: Any, fallback: str) -> str:
        s = str(text or "").strip().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s or fallback

    def migrate_diet_log_ids(self, data: Dict[str, Any]) -> None:
        logs = data.get("diet", {}).get("logs", {})
        if not isinstance(logs, dict):
            return

        for _, entry in logs.items():
            if not isinstance(entry, dict):
                continue
            checked = entry.setdefault("checked", {})
            if not isinstance(checked, dict):
                entry["checked"] = {}
                continue

            # Old V3/V4 ambiguous water key.
            if "water_hamidiye" in checked:
                old_value = bool(checked.get("water_hamidiye", False))
                checked.setdefault("water_hamidiye_1", old_value)
                checked.setdefault("water_hamidiye_2", old_value)
                checked.pop("water_hamidiye", None)

    # Diet helpers.
    def get_diet_config(self) -> Dict[str, Any]:
        return self.data["diet"]["config"]

    def _pretty_diet_template_name_from_path(self, path: Path) -> str:
        """Readable label for external diet config files.

        Example:
          diet_config_custom_BMR.json -> Custom BMR
        """
        stem = path.stem.strip()
        stem = re.sub(r"^diet[_\-\s]*config[_\-\s]*", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"[_\-]+", " ", stem).strip() or path.stem
        parts = []
        for part in stem.split():
            parts.append(part if part.isupper() else part.capitalize())
        return " ".join(parts) or path.stem

    def _unique_diet_template_name(self, templates: Dict[str, Dict[str, Any]], desired: str, path: Optional[Path] = None) -> str:
        base = stringify_value(desired) or (path.stem if path else "Diet Template")
        name = base
        if name not in templates:
            return name
        if path is not None:
            name = f"{base} ({path.name})"
            if name not in templates:
                return name
        counter = 2
        while f"{base} {counter}" in templates:
            counter += 1
        return f"{base} {counter}"

    def _add_diet_template_payload(self, templates: Dict[str, Dict[str, Any]], name: str, payload: Dict[str, Any], source_path: Optional[Path] = None) -> None:
        if not isinstance(payload, dict):
            return
        items = payload.get("items", [])
        if not isinstance(items, list):
            return
        display_name = self._unique_diet_template_name(templates, name, source_path)
        template_payload = dict(payload)
        if source_path is not None:
            template_payload.setdefault("_external_template_file", str(source_path))
        templates[display_name] = template_payload

    def external_diet_config_paths(self) -> List[Path]:
        """JSON diet configs the app can use as selectable templates.

        Supported locations:
          DATA/HealthTracker/DietTracker/diet_config_*.json
          DATA/HealthTracker/DietTracker/diet_configs/*.json

        The active DATA/HealthTracker/DietTracker/diet_config.json is excluded
        because it is already represented by "Current diet_config.json".
        """
        paths: List[Path] = []
        seen = set()

        candidates: List[Path] = []
        candidates.extend(sorted(self.diet_data_dir.glob("diet_config_*.json")))
        candidates.extend(sorted(self.diet_data_dir.glob("diet-config-*.json")))
        candidates.extend(sorted(self.diet_templates_dir.glob("*.json")))

        active = self.diet_config_path.resolve()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                if resolved == active:
                    continue
            except Exception:
                pass
            if candidate.name.lower() in {"diet_logs.json"}:
                continue
            paths.append(candidate)
        return paths

    def diet_template_map(self) -> Dict[str, Dict[str, Any]]:
        """Optional diet-template support.

        Sources:
          1. Inline templates inside diet_config.json under diet_templates/templates
          2. External files such as:
             DATA/HealthTracker/DietTracker/diet_config_custom_BMR.json
             DATA/HealthTracker/DietTracker/diet_configs/*.json

        The top-level diet_config.json remains available as the blank/current option.
        """
        config = self.get_diet_config()
        raw_templates = config.get("diet_templates", config.get("templates", {}))
        templates: Dict[str, Dict[str, Any]] = {}

        if isinstance(raw_templates, dict):
            for name, payload in raw_templates.items():
                display_name = stringify_value(name)
                if display_name and isinstance(payload, dict):
                    self._add_diet_template_payload(templates, display_name, payload)

        elif isinstance(raw_templates, list):
            for index, payload in enumerate(raw_templates, start=1):
                if not isinstance(payload, dict):
                    continue
                display_name = first_nonempty_string(
                    payload.get("name"),
                    payload.get("template_name"),
                    payload.get("title"),
                    f"Diet Template {index}",
                )
                if display_name:
                    self._add_diet_template_payload(templates, display_name, payload)

        for path in self.external_diet_config_paths():
            try:
                loaded = read_json(path)
                if not isinstance(loaded, dict):
                    continue
                display_name = first_nonempty_string(
                    loaded.get("template_name"),
                    loaded.get("name"),
                    loaded.get("title"),
                    self._pretty_diet_template_name_from_path(path),
                )
                self._add_diet_template_payload(templates, display_name, loaded, path)
            except Exception as exc:
                self.import_messages.append(f"Could not read diet template {path}: {exc}")

        return templates

    def diet_template_names(self) -> List[str]:
        return sorted(self.diet_template_map().keys(), key=lambda name: name.lower())

    def read_diet_template_settings(self) -> Dict[str, Any]:
        if not self.diet_template_settings_path.exists():
            return {}
        try:
            loaded = read_json(self.diet_template_settings_path)
            return loaded if isinstance(loaded, dict) else {}
        except Exception as exc:
            self.import_messages.append(f"Could not read diet_template_settings.json; using automatic default. Error: {exc}")
            return {}

    def write_diet_template_settings(self, settings: Dict[str, Any]) -> None:
        write_json(self.diet_template_settings_path, settings)

    def default_diet_template_name(self) -> str:
        templates = self.diet_template_map()
        settings = self.read_diet_template_settings()
        name = stringify_value(settings.get("default_diet_template", ""))
        if name and name in templates:
            return name

        # Backward compatibility: older V5.2/V5.3 stored the default inside
        # diet_config.json.  Read it, but no longer write new defaults there.
        config = self.get_diet_config()
        legacy_name = stringify_value(config.get("default_diet_template") or config.get("default_template") or "")
        if legacy_name and legacy_name in templates:
            return legacy_name

        # If external templates exist, one of them should be selected by default.
        names = sorted(templates.keys(), key=lambda item: item.lower())
        return names[0] if names else ""

    def set_default_diet_template_name(self, template_name: str) -> None:
        name = stringify_value(template_name)
        settings = self.read_diet_template_settings()
        if name:
            settings["default_diet_template"] = name
        else:
            settings.pop("default_diet_template", None)
        settings["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.write_diet_template_settings(settings)

    def diet_config_for_template(self, template_name: str = "") -> Dict[str, Any]:
        """Return the selected diet template as a config-like dict.

        Blank/unknown template names fall back to the top-level diet_config.json.
        Template entries inherit target/expenditure/notes from the top level unless
        they override them.
        """
        base = self.get_diet_config()
        name = stringify_value(template_name)
        if not name:
            name = self.default_diet_template_name()
        template = self.diet_template_map().get(name)
        if not isinstance(template, dict):
            return base

        return {
            "template_name": name,
            "target_calories": template.get("target_calories", base.get("target_calories", 0)),
            "estimated_expenditure": template.get("estimated_expenditure", base.get("estimated_expenditure", 0)),
            "notes": template.get("notes", base.get("notes", "")),
            "items": template.get("items", base.get("items", [])),
        }

    def diet_template_source_path(self, template_name: str = "") -> Optional[Path]:
        """File backing an editable diet template, or None if it is inline-only.

        An empty/unknown name maps to the active diet_config.json (the
        "Current diet_config.json" fallback option). External templates carry
        their source path in the synthetic ``_external_template_file`` key that
        diet_template_map() injects.
        """
        name = stringify_value(template_name)
        if not name:
            return self.diet_config_path
        payload = self.diet_template_map().get(name)
        if isinstance(payload, dict):
            source = stringify_value(payload.get("_external_template_file"))
            if source:
                return Path(source)
        return None

    def save_diet_template(self, template_name: str, edited: Dict[str, Any]) -> Path:
        """Write edited target/expenditure/notes/items back to a template file.

        Unknown keys already in the file are preserved (schema-flexible round
        trip). Editing a template only changes future blank days — saved logs
        keep their per-day frozen snapshots, so history is never rewritten.
        """
        path = self.diet_template_source_path(template_name)
        if path is None:
            raise ValueError(
                "This diet template is defined inline inside diet_config.json and "
                "cannot be edited as a standalone file yet."
            )

        base: Dict[str, Any] = {}
        if path.exists():
            try:
                loaded = read_json(path)
                if isinstance(loaded, dict):
                    base = loaded
            except Exception:
                base = {}

        base.pop("_external_template_file", None)
        base["target_calories"] = parse_float(edited.get("target_calories", 0), 0.0)
        base["estimated_expenditure"] = parse_float(edited.get("estimated_expenditure", 0), 0.0)
        base["notes"] = stringify_value(edited.get("notes", ""))
        base["items"] = [item for item in edited.get("items", []) if isinstance(item, dict)]

        normalized = self.normalize_diet_config(base)
        self.backup_file(path)
        write_json(path, normalized)

        # When the active diet_config.json is the one being edited, keep the
        # in-memory copy in sync so the checklist reflects the change at once.
        try:
            if path.resolve() == self.diet_config_path.resolve():
                self.data["diet"]["config"] = normalized
        except Exception:
            pass
        return path

    def _diet_template_file_path(self, display_name: str) -> Path:
        """A free file path under diet_configs/ for a new/renamed template."""
        base = self.safe_id(display_name, "diet_template")
        path = self.diet_templates_dir / f"{base}.json"
        counter = 2
        while path.exists():
            path = self.diet_templates_dir / f"{base}_{counter}.json"
            counter += 1
        return path

    def create_diet_template(self, name: str) -> Tuple[str, Path]:
        display = stringify_value(name)
        if not display:
            raise ValueError("Template name is required.")
        if display in self.diet_template_map():
            raise ValueError(f"A diet template named '{display}' already exists.")
        path = self._diet_template_file_path(display)
        payload = {
            "template_name": display,
            "target_calories": parse_float(DEFAULT_DIET_CONFIG.get("target_calories", 0), 0.0),
            "estimated_expenditure": parse_float(DEFAULT_DIET_CONFIG.get("estimated_expenditure", 0), 0.0),
            "notes": "",
            "items": [],
        }
        write_json(path, payload)
        return display, path

    def rename_diet_template(self, old_name: str, new_name: str) -> str:
        old = stringify_value(old_name)
        new = stringify_value(new_name)
        if not new:
            raise ValueError("New name is required.")
        if new == old:
            return new
        path = self.diet_template_source_path(old)
        if path is None or path.resolve() == self.diet_config_path.resolve():
            raise ValueError(
                "The active diet_config.json can't be renamed. Create a standalone template instead."
            )
        if new in self.diet_template_map():
            raise ValueError(f"A diet template named '{new}' already exists.")

        data: Dict[str, Any] = {}
        if path.exists():
            try:
                loaded = read_json(path)
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        data.pop("_external_template_file", None)
        data["template_name"] = new

        new_path = self._diet_template_file_path(new)
        write_json(new_path, self.normalize_diet_config(data))
        try:
            if path.exists() and path.resolve() != new_path.resolve():
                path.unlink()
        except Exception:
            pass

        settings = self.read_diet_template_settings()
        if stringify_value(settings.get("default_diet_template")) == old:
            self.set_default_diet_template_name(new)
        return new

    def delete_diet_template(self, name: str) -> None:
        target = stringify_value(name)
        path = self.diet_template_source_path(target)
        if path is None or path.resolve() == self.diet_config_path.resolve():
            raise ValueError("The active diet_config.json can't be deleted.")
        if path.exists():
            self.backup_file(path)
            path.unlink()
        settings = self.read_diet_template_settings()
        if stringify_value(settings.get("default_diet_template")) == target:
            self.set_default_diet_template_name("")

    def create_workout_template(self, name: str) -> str:
        display = stringify_value(name)
        if not display:
            raise ValueError("Template name is required.")
        templates = self.get_templates()
        if display in templates:
            raise ValueError(f"A workout template named '{display}' already exists.")
        templates[display] = WorkoutTemplate(
            name=display, exercises=[], warmup_notes="", extra={"_default_rest_seconds": 75}
        )
        self.set_templates(templates)
        return display

    def rename_workout_template(self, old_name: str, new_name: str) -> str:
        old = stringify_value(old_name)
        new = stringify_value(new_name)
        if not new:
            raise ValueError("New name is required.")
        if new == old:
            return new
        templates = self.get_templates()
        if old not in templates:
            raise ValueError(f"Workout template '{old}' was not found.")
        if new in templates:
            raise ValueError(f"A workout template named '{new}' already exists.")

        rebuilt: Dict[str, WorkoutTemplate] = {}
        for key, template in templates.items():
            if key == old:
                template.name = new
                rebuilt[new] = template
            else:
                rebuilt[key] = template
        self.set_templates(rebuilt)
        if self.get_last_template() == old:
            self.set_last_template(new)
        return new

    def delete_workout_template(self, name: str) -> None:
        target = stringify_value(name)
        templates = self.get_templates()
        if target not in templates:
            raise ValueError(f"Workout template '{target}' was not found.")
        del templates[target]
        self.set_templates(templates)
        if self.get_last_template() == target:
            self.set_last_template("")

    def get_diet_log(self, date_text: str) -> Dict[str, Any]:
        logs = self.data["diet"].setdefault("logs", {})
        if date_text not in logs:
            logs[date_text] = {"checked": {}, "note": "", "weight_kg": "", "additional_calories": "", "additional_deficit": ""}
        return logs[date_text]

    def save_diet_log(self, date_text: str, log_entry: Dict[str, Any]) -> None:
        log_entry["saved_at"] = datetime.now().isoformat(timespec="seconds")
        self.data["diet"].setdefault("logs", {})[date_text] = log_entry
        write_json(self.diet_logs_path, self.data["diet"].get("logs", {}))

    def delete_diet_log(self, date_text: str) -> None:
        logs = self.data["diet"].setdefault("logs", {})
        if date_text in logs:
            del logs[date_text]
            write_json(self.diet_logs_path, logs)

    # Workout helpers.
    def get_templates(self) -> Dict[str, WorkoutTemplate]:
        return deserialize_templates(self.data["workout"].get("templates", {}))

    def set_templates(self, templates: Dict[str, WorkoutTemplate]) -> None:
        self.data["workout"]["templates"] = serialize_templates(templates)
        write_json(self.workout_templates_path, self.data["workout"]["templates"])

    def workout_history(self) -> List[dict]:
        return self.data["workout"].setdefault("history", [])

    def save_workout_history_file(self) -> None:
        write_json(
            self.workout_history_path,
            {
                "history": self.data["workout"].get("history", []),
                "settings": self.data["workout"].get("settings", {"last_selected_template": ""}),
            },
        )

    def sorted_workout_history(self) -> List[dict]:
        return sorted(
            self.workout_history(),
            key=lambda e: (e.get("date", ""), e.get("template", ""), e.get("created_at", "")),
            reverse=True,
        )

    def add_workout_entry(self, entry: dict) -> None:
        self.workout_history().append(entry)
        self.save_workout_history_file()

    def update_workout_entry(self, old_entry: dict, new_entry: dict) -> None:
        history = self.workout_history()
        for idx, entry in enumerate(history):
            if entry is old_entry or entry == old_entry:
                history[idx] = new_entry
                self.save_workout_history_file()
                return
        raise ValueError("Workout entry not found.")

    def delete_workout_entry(self, old_entry: dict) -> None:
        history = self.workout_history()
        for idx, entry in enumerate(history):
            if entry is old_entry or entry == old_entry:
                del history[idx]
                self.save_workout_history_file()
                return
        raise ValueError("Workout entry not found.")

    def get_last_template(self) -> str:
        return self.data["workout"].setdefault("settings", {}).get("last_selected_template", "")

    def set_last_template(self, template_name: str) -> None:
        self.data["workout"].setdefault("settings", {})["last_selected_template"] = template_name
        self.save_workout_history_file()
# -----------------------------
# Diet UI
# -----------------------------
class DietChecklistPage(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.check_vars: Dict[str, QCheckBox] = {}
        self.current_date = date.today().isoformat()
        self.loading = False
        self.rendered_date = ""
        self.rendered_force_current_config = False
        self.rendered_items: List[Dict[str, Any]] = []

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous day")
        self.today_btn = QPushButton("Today")
        self.next_btn = QPushButton("Next day →")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.select_all_btn = QPushButton("Select all")
        self.clear_selected_btn = QPushButton("Clear selected")
        self.reload_btn = QPushButton("Reload config")
        self.diet_template_combo = QComboBox()
        self.diet_template_combo.setMinimumWidth(180)
        self.make_default_diet_template_btn = QPushButton("Make default")
        self.make_default_diet_template_btn.setToolTip("Use this diet template automatically for new blank days.")
        self.edit_diet_template_btn = QPushButton("Edit template…")
        self.edit_diet_template_btn.setToolTip("Edit this diet template's items, target, and expenditure. Saved days keep their frozen snapshots.")
        self.manage_diet_template_btn = QPushButton("Manage ▾")
        self.manage_diet_template_btn.setToolTip("Create, rename, or delete diet templates.")
        manage_menu = QMenu(self.manage_diet_template_btn)
        self.new_diet_template_action = manage_menu.addAction("New template…")
        self.rename_diet_template_action = manage_menu.addAction("Rename template…")
        self.delete_diet_template_action = manage_menu.addAction("Delete template…")
        self.manage_diet_template_btn.setMenu(manage_menu)

        top.addWidget(self.prev_btn)
        top.addWidget(self.today_btn)
        top.addWidget(self.date_edit)
        top.addWidget(self.next_btn)
        top.addWidget(QLabel("Diet template:"))
        top.addWidget(self.diet_template_combo)
        top.addWidget(self.make_default_diet_template_btn)
        top.addWidget(self.edit_diet_template_btn)
        top.addWidget(self.manage_diet_template_btn)
        top.addStretch(1)
        top.addWidget(self.select_all_btn)
        top.addWidget(self.clear_selected_btn)
        top.addWidget(self.reload_btn)
        root.addLayout(top)

        autosave_note = QLabel("Diet checklist autosaves in real time. No manual Save button needed.")
        autosave_note.setStyleSheet("color: #888888; font-size: 11px;")
        root.addWidget(autosave_note)

        splitter = QSplitter()

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)

        self.scroll_widget = QWidget()
        self.items_layout = QVBoxLayout(self.scroll_widget)
        self.items_layout.setContentsMargins(6, 6, 6, 6)
        self.items_layout.setSpacing(5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.scroll_widget)
        left_layout.addWidget(scroll)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        summary_box = QGroupBox("Daily diet summary")
        summary_grid = QGridLayout(summary_box)
        self.summary_labels: Dict[str, QLabel] = {}
        rows = [
            ("Plan Total", "plan_total"),
            ("Eaten", "consumed"),
            ("Deficit", "deficit_pos"),
            ("Surplus", "surplus"),
        ]
        for row, (label, key) in enumerate(rows):
            summary_grid.addWidget(QLabel(label + ":"), row, 0)
            value = QLabel("")
            value.setStyleSheet("font-weight: bold;")
            summary_grid.addWidget(value, row, 1)
            self.summary_labels[key] = value
        right_layout.addWidget(summary_box)

        log_box = QGroupBox("Optional diet log / manual adjustments")
        log_layout = QVBoxLayout(log_box)

        self.weight_edit = QLineEdit()
        self.weight_edit.setPlaceholderText("Morning / daily weight kg")

        self.additional_calories_edit = QLineEdit()
        self.additional_calories_edit.setPlaceholderText("Extra unlisted food/snack calories, e.g. 150")

        self.additional_deficit_edit = QLineEdit()
        self.additional_deficit_edit.setPlaceholderText("Extra deficit/burn adjustment, e.g. 200")

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Diet notes")

        self.steps_edit = QLineEdit()
        self.steps_edit.setPlaceholderText("steps")
        self.steps_edit.setMaximumWidth(90)

        self.step_weight_edit = QLineEdit()
        self.step_weight_edit.setPlaceholderText("kg")
        self.step_weight_edit.setMaximumWidth(70)

        self.step_result_label = QLabel("= 0 kcal")
        self.step_result_label.setStyleSheet("font-weight: bold;")
        self.step_formula_label = QLabel(f"× {STEP_CALORIE_COEFFICIENT:g}")

        step_line = QHBoxLayout()
        step_line.addWidget(QLabel("Step burn:"))
        step_line.addWidget(self.steps_edit)
        step_line.addWidget(QLabel("steps ×"))
        step_line.addWidget(self.step_weight_edit)
        step_line.addWidget(QLabel("kg"))
        step_line.addWidget(self.step_formula_label)
        step_line.addWidget(self.step_result_label)
        step_line.addStretch(1)

        log_layout.addWidget(QLabel("Weight kg:"))
        log_layout.addWidget(self.weight_edit)
        log_layout.addWidget(QLabel("Additional calories:"))
        log_layout.addWidget(self.additional_calories_edit)
        log_layout.addWidget(QLabel("Additional deficit / burned calories:"))
        log_layout.addWidget(self.additional_deficit_edit)
        log_layout.addLayout(step_line)
        log_layout.addWidget(QLabel("Notes:"))
        log_layout.addWidget(self.notes_edit, 1)
        right_layout.addWidget(log_box, 1)

        splitter.addWidget(left_container)
        splitter.addWidget(right)
        splitter.setSizes([700, 430])
        root.addWidget(splitter, 1)

        self.prev_btn.clicked.connect(lambda: self.shift_day(-1))
        self.next_btn.clicked.connect(lambda: self.shift_day(1))
        self.today_btn.clicked.connect(self.go_today)
        self.date_edit.dateChanged.connect(self.on_date_changed)
        self.select_all_btn.clicked.connect(self.select_all_items)
        self.clear_selected_btn.clicked.connect(self.clear_selected_items)
        self.reload_btn.clicked.connect(self.reload_diet_config_clicked)
        self.diet_template_combo.currentIndexChanged.connect(self.on_diet_template_changed)
        self.make_default_diet_template_btn.clicked.connect(self.make_selected_diet_template_default)
        self.edit_diet_template_btn.clicked.connect(self.edit_selected_diet_template)
        self.new_diet_template_action.triggered.connect(self.new_diet_template)
        self.rename_diet_template_action.triggered.connect(self.rename_selected_diet_template)
        self.delete_diet_template_action.triggered.connect(self.delete_selected_diet_template)

        # Free-text fields now autosave too, so the old Save button is unnecessary.
        self.weight_edit.textChanged.connect(self.on_free_text_changed)
        self.additional_calories_edit.textChanged.connect(self.on_free_text_changed)
        self.additional_deficit_edit.textChanged.connect(self.on_free_text_changed)
        self.additional_calories_edit.returnPressed.connect(lambda: self.evaluate_adjustment_field(self.additional_calories_edit))
        self.additional_deficit_edit.returnPressed.connect(lambda: self.evaluate_adjustment_field(self.additional_deficit_edit))
        self.notes_edit.textChanged.connect(self.on_free_text_changed)

        self.steps_edit.textChanged.connect(self.update_step_calculator)
        self.step_weight_edit.textChanged.connect(self.update_step_calculator)

        self.refresh_diet_template_combo()
        self.rebuild_items()
        self.load_day(self.current_date)

    def selected_date_text(self) -> str:
        return self.date_edit.date().toString("yyyy-MM-dd")

    def selected_diet_template_name(self) -> str:
        data = self.diet_template_combo.currentData()
        return stringify_value(data)

    def refresh_diet_template_combo(self, preferred_name: str = "") -> None:
        default_name = self.store.default_diet_template_name()
        template_names = self.store.diet_template_names()
        current_name = preferred_name or self.selected_diet_template_name() or default_name
        self.loading = True
        try:
            self.diet_template_combo.clear()

            if template_names:
                # V5.4/V5.5: external diet configs are now the real template choices.
                # Hide the old confusing "Current diet_config.json" option.
                for template_name in template_names:
                    label = template_name
                    if template_name == default_name:
                        label += " (default)"
                    self.diet_template_combo.addItem(label, template_name)

                index = self.diet_template_combo.findData(current_name)
                if index < 0 and default_name:
                    index = self.diet_template_combo.findData(default_name)
                self.diet_template_combo.setCurrentIndex(index if index >= 0 else 0)
            else:
                # Fallback for users who still keep only the legacy single
                # diet_config.json file and no external templates.
                self.diet_template_combo.addItem("Current diet_config.json (default)", "")
                self.diet_template_combo.setCurrentIndex(0)
        finally:
            self.loading = False

    def make_selected_diet_template_default(self) -> None:
        selected = self.selected_diet_template_name()
        self.store.set_default_diet_template_name(selected)
        self.refresh_diet_template_combo(selected)
        label = selected or "Current diet_config.json"
        QMessageBox.information(
            self,
            APP_TITLE,
            f"Default diet template set to:\n\n{label}\n\nNew blank days will use this automatically. Existing saved days keep their frozen snapshots."
        )

    def edit_selected_diet_template(self) -> None:
        template_name = self.selected_diet_template_name()
        if self.store.diet_template_source_path(template_name) is None:
            QMessageBox.information(
                self,
                APP_TITLE,
                "This diet template is defined inline inside diet_config.json and can't be edited in-app yet.\n\n"
                "Edit it via the JSON file, or create a standalone template instead.",
            )
            return

        config = self.store.diet_config_for_template(template_name)
        dialog = DietTemplateEditDialog(self, template_name, config)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.store.save_diet_template(template_name, dialog.get_config())
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, f"Could not save the diet template.\n\n{exc}")
            return

        # Reload split files so the edited template/config is picked up, then
        # rebuild the *visible* checklist from current config. Saved days keep
        # their frozen per-day snapshots — only blank/unsaved days change.
        self.store.load_split_files()
        self.refresh_diet_template_combo(template_name)
        self.rebuild_items(force_current_config=True)
        QMessageBox.information(
            self,
            APP_TITLE,
            "Diet template saved. Previously logged days keep their frozen items; "
            "new blank days use the updated template.",
        )

    def new_diet_template(self) -> None:
        name, ok = QInputDialog.getText(self, APP_TITLE, "Name for the new diet template:")
        if not ok or not stringify_value(name):
            return
        try:
            display, path = self.store.create_diet_template(name)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return

        self.store.load_split_files()
        # Open the editor right away so the user fills the empty template.
        config = self.store.diet_config_for_template(display)
        dialog = DietTemplateEditDialog(self, display, config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.save_diet_template(display, dialog.get_config())
            except Exception as exc:
                QMessageBox.warning(self, APP_TITLE, f"Could not save the diet template.\n\n{exc}")
        else:
            # Cancelled before adding anything — drop the empty starter file.
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

        self.store.load_split_files()
        self.refresh_diet_template_combo(display)
        self.rebuild_items(force_current_config=True)

    def rename_selected_diet_template(self) -> None:
        old = self.selected_diet_template_name()
        if self.store.diet_template_source_path(old) is None or not old:
            QMessageBox.information(
                self, APP_TITLE,
                "This entry can't be renamed in-app. Create a standalone template instead.",
            )
            return
        new, ok = QInputDialog.getText(self, APP_TITLE, "New name for this diet template:", text=old)
        if not ok or not stringify_value(new):
            return
        try:
            display = self.store.rename_diet_template(old, new)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return
        self.store.load_split_files()
        self.refresh_diet_template_combo(display)
        self.rebuild_items(force_current_config=True)

    def delete_selected_diet_template(self) -> None:
        target = self.selected_diet_template_name()
        if self.store.diet_template_source_path(target) is None or not target:
            QMessageBox.information(
                self, APP_TITLE,
                "This entry can't be deleted in-app.",
            )
            return
        confirm = QMessageBox.question(
            self, APP_TITLE,
            f"Delete diet template '{target}'?\n\nSaved days that used it keep their frozen snapshots.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_diet_template(target)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return
        self.store.load_split_files()
        self.refresh_diet_template_combo()
        self.rebuild_items(force_current_config=True)

    def set_diet_template_combo(self, template_name: str) -> None:
        index = self.diet_template_combo.findData(stringify_value(template_name))
        self.loading = True
        try:
            self.diet_template_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.loading = False

    def reload_diet_config_clicked(self) -> None:
        # Reload split JSON files so manual diet_config.json edits and newly added
        # diet_templates are visible without restarting the app.
        preferred = self.selected_diet_template_name()
        self.store.load_split_files()
        self.refresh_diet_template_combo(preferred)
        self.rebuild_items(force_current_config=True)

    def on_diet_template_changed(self) -> None:
        if self.loading:
            return

        date_text = self.current_date or self.selected_date_text()
        logs = self.store.data.get("diet", {}).get("logs", {})
        existing_log = logs.get(date_text, {}) if isinstance(logs.get(date_text, {}), dict) else {}

        if existing_log:
            has_checked = any(bool(v) for v in existing_log.get("checked", {}).values()) if isinstance(existing_log.get("checked", {}), dict) else False
            has_manual = any(stringify_value(existing_log.get(k)) for k in ("weight_kg", "additional_calories", "additional_deficit", "note"))
            if has_checked or has_manual:
                choice = QMessageBox.question(
                    self,
                    APP_TITLE,
                    "This date already has saved diet data. Changing the template will rebuild the visible checklist for this date. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if choice != QMessageBox.StandardButton.Yes:
                    self.set_diet_template_combo(existing_log.get("diet_template_name", ""))
                    return

        selected_template_name = self.selected_diet_template_name()
        self.rebuild_items(date_text=date_text, force_current_config=True)

        # V5.3: changing the dropdown is now an actual per-day template change.
        # Rebuild/load can reset the combo to the old log value, so restore the
        # chosen template and immediately freeze the new template's items, target,
        # and expenditure into this date. This prevents exports from keeping old
        # 1610/1939 snapshots after switching to an external config such as Custom BMR.
        self.set_diet_template_combo(selected_template_name)
        self.rendered_force_current_config = True
        self.save_current_day(date_text)
        self.update_summary()

    def on_date_changed(self) -> None:
        if self.loading:
            return

        # V3.4:
        # Do NOT save the old date just because the user navigated away.
        # Autosave already runs when the user actually changes a checkbox/text
        # field. Saving on navigation was polluting old logs with the newest
        # diet_config.json before they had a proper frozen snapshot.
        self.load_day(self.selected_date_text())

    def shift_day(self, amount: int) -> None:
        self.date_edit.setDate(self.date_edit.date().addDays(amount))

    def go_today(self) -> None:
        self.date_edit.setDate(QDate.currentDate())

    def rebuild_items(self, date_text: Optional[str] = None, force_current_config: bool = False, load_after: bool = True) -> None:
        # Rebuild the visible checklist for a specific date.
        # V3.3: saved diet days can carry their own item snapshot, so old history
        # does not have to be displayed through the newest diet_config.json.
        date_text = date_text or self.selected_date_text()

        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.check_vars = {}
        selected_template_name = self.selected_diet_template_name()
        logs = self.store.data.get("diet", {}).get("logs", {})
        log = logs.get(date_text)
        has_saved_log = isinstance(log, dict)
        has_snapshot = has_saved_log and isinstance(log.get("items_snapshot"), list) and bool(log.get("items_snapshot"))
        has_checked_legacy = has_saved_log and isinstance(log.get("checked"), dict) and bool(log.get("checked"))

        if force_current_config or not has_saved_log:
            template_config = self.store.diet_config_for_template(selected_template_name)
            items = diet_items_snapshot(template_config.get("items", []))
        elif has_snapshot or has_checked_legacy:
            items = diet_log_items(self.store, date_text, force_current_config=False)
        else:
            template_config = self.store.diet_config_for_template(selected_template_name)
            items = diet_items_snapshot(template_config.get("items", []))
        self.rendered_items = diet_items_snapshot(items)
        self.rendered_date = date_text
        self.rendered_force_current_config = force_current_config

        categories: List[str] = []
        for item in self.rendered_items:
            cat = item.get("category", "Other")
            if cat not in categories:
                categories.append(cat)

        status = diet_snapshot_status(self.store, date_text)
        if status == "frozen" and not force_current_config:
            snapshot_message = "This day is using a frozen item snapshot."
        elif self.store.data.get("diet", {}).get("logs", {}).get(date_text) and not force_current_config:
            snapshot_message = "Legacy unsnapped day: showing only item IDs found in this log. Freeze it from backup for exact old calories."
        else:
            template_name = self.selected_diet_template_name()
            snapshot_message = f"This day is using diet template: {template_name}." if template_name else "This day is using the current diet_config.json."
        snapshot_note = QLabel(snapshot_message)
        snapshot_note.setStyleSheet("color: #888888; font-size: 11px;")
        self.items_layout.addWidget(snapshot_note)

        # First-run / empty template: don't strand the user on a blank checklist —
        # offer a clear way into the editor instead.
        if not self.rendered_items:
            empty = QLabel("This diet template has no items yet.")
            empty.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 16px;")
            empty.setWordWrap(True)
            self.items_layout.addWidget(empty)
            create_btn = QPushButton("Create your first item →")
            create_btn.setToolTip("Open the template editor to add diet items.")
            create_btn.clicked.connect(self.edit_selected_diet_template)
            self.items_layout.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignLeft)
            self.items_layout.addStretch(1)
            if load_after:
                self.load_day(date_text, rebuild_if_needed=False)
            return

        for category in categories:
            header = QLabel(category)
            header.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
            self.items_layout.addWidget(header)

            for item in self.rendered_items:
                if item.get("category", "Other") != category:
                    continue

                item_id = str(item.get("id", ""))
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)

                cb = QCheckBox()
                cb.toggled.connect(self.on_check_changed)
                self.check_vars[item_id] = cb

                calories = parse_float(item.get("calories", 0), 0.0)

                text = QLabel(diet_item_checklist_label(item))
                text.setWordWrap(True)
                kcal = QLabel(f"{calories:.2f} kcal")
                kcal.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                kcal.setMinimumWidth(95)

                row_layout.addWidget(cb)
                row_layout.addWidget(text, 1)
                row_layout.addWidget(kcal)
                self.items_layout.addWidget(row)

        self.items_layout.addStretch(1)
        if load_after:
            self.load_day(date_text, rebuild_if_needed=False)

    def load_day(self, date_text: str, rebuild_if_needed: bool = True) -> None:
        # Read existing log without creating a new blank day.
        logs = self.store.data.get("diet", {}).get("logs", {})
        existing = logs.get(date_text)
        log_exists = isinstance(existing, dict)
        log = existing if log_exists else {"checked": {}, "note": "", "weight_kg": "", "additional_calories": "", "additional_deficit": ""}

        # Empty/new days use the configured default diet template. Saved days use
        # their own stored diet_template_name and/or frozen item snapshot.
        desired_template = stringify_value(log.get("diet_template_name", "")) if log_exists else self.store.default_diet_template_name()
        self.set_diet_template_combo(desired_template)

        if rebuild_if_needed and self.rendered_date != date_text:
            self.rebuild_items(date_text=date_text, force_current_config=False, load_after=False)

        self.loading = True
        self.current_date = date_text

        checked = log.get("checked", {}) if isinstance(log, dict) else {}
        for item_id, cb in self.check_vars.items():
            cb.setChecked(bool(checked.get(item_id, False)))

        self.weight_edit.setText(str(log.get("weight_kg", "")))
        self.additional_calories_edit.setText(str(log.get("additional_calories", "")))
        self.additional_deficit_edit.setText(str(log.get("additional_deficit", "")))
        self.notes_edit.setPlainText(log.get("note", ""))

        self.loading = False
        self.update_summary()
        self.update_step_calculator()

    def calculated_step_burn(self) -> float:
        steps = parse_steps(self.steps_edit.text())
        weight = parse_float(self.step_weight_edit.text(), 0.0)
        return max(steps * weight * STEP_CALORIE_COEFFICIENT, 0.0)

    def update_step_calculator(self) -> None:
        burned = self.calculated_step_burn()
        self.step_result_label.setText(f"= {burned:.0f} kcal")

    def evaluate_adjustment_field(self, field: QLineEdit) -> None:
        """Turn a typed kcal expression like 120+33 into 153 when Enter is pressed."""
        raw_text = field.text().strip()
        if not raw_text:
            return

        result = calculate_number_expression(raw_text)
        if result is None:
            QMessageBox.warning(
                self,
                APP_TITLE,
                "Could not calculate this value.\n\n"
                "Use simple math only, for example:\n"
                "120+33\n"
                "120-20\n"
                "120*2\n"
                "120/2"
            )
            return

        # Calories are usually whole numbers. Keep decimals only when needed.
        formatted = format_number(result, decimals=2)
        field.setText(formatted)
        self.save_current_day()

    def select_all_items(self) -> None:
        self.loading = True
        for cb in self.check_vars.values():
            cb.setChecked(True)
        self.loading = False
        self.save_current_day()

    def clear_selected_items(self) -> None:
        self.loading = True
        for cb in self.check_vars.values():
            cb.setChecked(False)
        self.loading = False
        self.save_current_day()

    def save_current_day(self, date_text: Optional[str] = None) -> None:
        if self.loading:
            return

        # Use the active loaded date by default, not necessarily the date currently
        # displayed in the date picker. This prevents date-navigation from cloning
        # today's checklist into the next/previous day.
        date_text = date_text or self.current_date

        logs = self.store.data.get("diet", {}).get("logs", {})
        existing_log = logs.get(date_text, {}) if isinstance(logs.get(date_text, {}), dict) else {}
        selected_template_name = self.selected_diet_template_name()
        config = self.store.diet_config_for_template(selected_template_name)

        # V3.3: save the item list/calories that are visible for this date.
        # Existing snapshot values are preserved when editing an old frozen day.
        items_snapshot = diet_items_snapshot(self.rendered_items or diet_log_items(self.store, date_text))
        target_snapshot = (
            parse_float(config.get("target_calories", 0), 0.0)
            if self.rendered_force_current_config or "target_calories_snapshot" not in existing_log
            else parse_float(existing_log.get("target_calories_snapshot"), 0.0)
        )
        expenditure_snapshot = (
            parse_float(config.get("estimated_expenditure", 0), 0.0)
            if self.rendered_force_current_config or "estimated_expenditure_snapshot" not in existing_log
            else parse_float(existing_log.get("estimated_expenditure_snapshot"), 0.0)
        )

        entry = {
            "checked": {item_id: cb.isChecked() for item_id, cb in self.check_vars.items()},
            "items_snapshot": items_snapshot,
            "diet_template_name": selected_template_name,
            "target_calories_snapshot": target_snapshot,
            "estimated_expenditure_snapshot": expenditure_snapshot,
            "weight_kg": self.weight_edit.text().strip(),
            "additional_calories": self.additional_calories_edit.text().strip(),
            "additional_deficit": self.additional_deficit_edit.text().strip(),
            "note": self.notes_edit.toPlainText().strip(),
        }

        # Do not create a brand-new diet history entry just because the user opened
        # or navigated through an empty day. If the date already exists, still save
        # the empty state so "Clear selected" can intentionally clear a real log.
        has_any_checked = any(entry["checked"].values())
        has_manual_data = any(
            str(entry.get(key, "")).strip()
            for key in ("weight_kg", "additional_calories", "additional_deficit", "note")
        )

        has_template_choice = bool(selected_template_name)
        if not has_any_checked and not has_manual_data and not has_template_choice and date_text not in logs:
            self.update_summary()
            return

        self.store.save_diet_log(date_text, entry)
        self.update_summary()

    def on_check_changed(self) -> None:
        if not self.loading:
            self.save_current_day()

    def on_free_text_changed(self) -> None:
        if not self.loading:
            self.save_current_day()

    def calculate_summary(self) -> Dict[str, Any]:
        items = self.rendered_items or diet_log_items(self.store, self.current_date)
        logs = self.store.data.get("diet", {}).get("logs", {})
        if self.current_date not in logs:
            selected_config = self.store.diet_config_for_template(self.selected_diet_template_name())
            target = parse_float(selected_config.get("target_calories", 0), 0.0)
            expenditure = parse_float(selected_config.get("estimated_expenditure", 0), 0.0)
        else:
            target = diet_target_for_log(self.store, self.current_date)
            expenditure = diet_expenditure_for_log(self.store, self.current_date)
        plan_total = sum(parse_float(item.get("calories", 0), 0.0) for item in items)

        checklist_consumed = 0.0
        checked_count = 0
        for item in items:
            item_id = str(item.get("id", ""))
            if self.check_vars.get(item_id) and self.check_vars[item_id].isChecked():
                checklist_consumed += parse_float(item.get("calories", 0), 0.0)
                checked_count += 1

        summary = compute_diet_energy(
            plan_total=plan_total,
            checklist_consumed=checklist_consumed,
            additional_calories=parse_float(self.additional_calories_edit.text(), 0.0),
            additional_deficit=parse_float(self.additional_deficit_edit.text(), 0.0),
            target=target,
            expenditure=expenditure,
        )
        summary["checked_count"] = checked_count
        summary["total_count"] = len(items)
        return summary

    def update_summary(self) -> None:
        s = self.calculate_summary()
        self.summary_labels["plan_total"].setText(f"{s['plan_total']:.0f} kcal")
        self.summary_labels["consumed"].setText(f"{s['consumed']:.0f} kcal")
        self.summary_labels["deficit_pos"].setText(f"{s['deficit_pos']:.0f} kcal")
        self.summary_labels["surplus"].setText(f"{s['surplus']:.0f} kcal")


class DietHistoryPage(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.visible_dates: List[str] = []

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by date or note...")
        self.refresh_btn = QPushButton("Refresh")
        self.delete_btn = QPushButton("Delete selected")
        top.addWidget(self.search_edit, 1)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.delete_btn)
        root.addLayout(top)

        splitter = QSplitter()
        self.list_widget = QListWidget()
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.details)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, 1)

        button_row = QHBoxLayout()
        self.export_selected_btn = QPushButton("Extract selected to Markdown")
        self.export_all_btn = QPushButton("Export all diet history")
        self.pdf_all_btn = QPushButton("PDF: All Dates")
        self.pdf_last7_btn = QPushButton("PDF: Last 7 Dates")
        self.pdf_range_btn = QPushButton("PDF: Custom Range")
        button_row.addWidget(self.pdf_all_btn)
        button_row.addWidget(self.pdf_last7_btn)
        button_row.addWidget(self.pdf_range_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.export_all_btn)
        button_row.addWidget(self.export_selected_btn)
        root.addLayout(button_row)

        self.search_edit.textChanged.connect(self.refresh)
        self.refresh_btn.clicked.connect(self.refresh)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.export_selected_btn.clicked.connect(self.export_selected_to_markdown)
        self.export_all_btn.clicked.connect(self.export_all_history)
        self.pdf_all_btn.clicked.connect(self.export_diet_pdf_all_clicked)
        self.pdf_last7_btn.clicked.connect(self.export_diet_pdf_last7_clicked)
        self.pdf_range_btn.clicked.connect(self.export_diet_pdf_custom_range_clicked)
        self.list_widget.currentRowChanged.connect(self.show_details)
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        self.visible_dates = []

        query = self.search_edit.text().strip().lower()
        logs = self.store.data.get("diet", {}).get("logs", {})
        for date_text in sorted(logs.keys(), reverse=True):
            entry = logs.get(date_text, {})
            haystack = f"{date_text} {entry.get('note', '')} {entry.get('weight_kg', '')}".lower()
            if query and query not in haystack:
                continue

            self.visible_dates.append(date_text)
            summary = self.summary_for_date(date_text)
            text = f"{date_text} | {summary['checked']}/{summary['total']} | {format_deficit_or_surplus(summary['deficit'])}"
            weight = entry.get("weight_kg", "")
            if weight:
                text += f" | {weight} kg"
            self.list_widget.addItem(text)

        if self.visible_dates:
            self.list_widget.setCurrentRow(0)
        else:
            self.details.setPlainText("No diet history found.")

    def summary_for_date(self, date_text: str) -> Dict[str, Any]:
        items = diet_log_items(self.store, date_text)
        target = diet_target_for_log(self.store, date_text)
        expenditure = diet_expenditure_for_log(self.store, date_text)
        log = self.store.data["diet"].get("logs", {}).get(date_text, {})
        checked = log.get("checked", {}) if isinstance(log, dict) else {}

        checklist_consumed = 0.0
        checked_count = 0
        for item in items:
            item_id = str(item.get("id", ""))
            if checked.get(item_id, False):
                checklist_consumed += parse_float(item.get("calories", 0), 0.0)
                checked_count += 1

        summary = compute_diet_energy(
            plan_total=sum(parse_float(item.get("calories", 0), 0.0) for item in items),
            checklist_consumed=checklist_consumed,
            additional_calories=parse_float(log.get("additional_calories", ""), 0.0),
            additional_deficit=parse_float(log.get("additional_deficit", ""), 0.0),
            target=target,
            expenditure=expenditure,
        )
        summary["checked"] = checked_count
        summary["total"] = len(items)
        summary["snapshot_status"] = diet_snapshot_status(self.store, date_text)
        return summary

    def delete_selected(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.visible_dates):
            QMessageBox.information(self, APP_TITLE, "Select a diet history day first.")
            return

        date_text = self.visible_dates[row]
        confirm = QMessageBox.question(
            self,
            APP_TITLE,
            f"Delete diet log for {date_text}?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.store.delete_diet_log(date_text)
        self.refresh()

    def show_details(self, row: int) -> None:
        if row < 0 or row >= len(self.visible_dates):
            self.details.setPlainText("Select a diet day.")
            return

        date_text = self.visible_dates[row]
        self.details.setPlainText(self.entry_to_plain_text(date_text))

    def entry_to_plain_text(self, date_text: str) -> str:
        items = diet_log_items(self.store, date_text)
        log = self.store.data["diet"].get("logs", {}).get(date_text, {})
        checked = log.get("checked", {})
        summary = self.summary_for_date(date_text)

        lines = [f"Date: {date_text}\n"]
        if log.get("diet_template_name"):
            lines.append(f"Diet template: {log.get('diet_template_name')}\n")
        lines.append(f"Diet item source: {diet_snapshot_status(self.store, date_text)}\n")
        if log.get("weight_kg"):
            lines.append(f"Weight: {log.get('weight_kg')} kg\n")
        if summary["additional_calories"]:
            lines.append(f"Additional calories: {summary['additional_calories']:.0f} kcal\n")
        if summary["additional_deficit"]:
            lines.append(f"Additional deficit: {summary['additional_deficit']:.0f} kcal\n")
        lines.append("\nChecklist:\n")

        for item in items:
            item_id = str(item.get("id", ""))
            is_checked = bool(checked.get(item_id, False))
            mark = "✓" if is_checked else " "
            kcal = float(item.get("calories", 0))
            lines.append(f"[{mark}] {item.get('name', item_id)} — {kcal:.2f} kcal\n")

        lines.append(f"\nChecklist calories eaten: {summary['checklist_consumed']:.0f} kcal\n")
        lines.append(f"Additional calories: {summary['additional_calories']:.0f} kcal\n")
        lines.append(f"Total calories eaten: {summary['consumed']:.0f} kcal\n")
        lines.append(f"Net calories for target after deficit adjustment: {summary['adjusted_consumed']:.0f} kcal\n")
        lines.append(f"Calories remaining to target: {summary['remaining']:.0f} kcal\n")
        lines.append(f"Calories over target: {summary['over']:.0f} kcal\n")
        lines.append(f"Additional deficit: {summary['additional_deficit']:.0f} kcal\n")
        lines.append(f"Estimated deficit today: {summary['deficit']:.0f} kcal\n")
        if log.get("note"):
            lines.append(f"\nNotes:\n{log.get('note')}\n")
        return "".join(lines)

    def entry_to_markdown(self, date_text: str) -> str:
        items = diet_log_items(self.store, date_text)
        log = self.store.data["diet"].get("logs", {}).get(date_text, {})
        checked = log.get("checked", {})
        summary = self.summary_for_date(date_text)

        lines = [f"# Diet Log — {date_text}\n\n"]
        if log.get("diet_template_name"):
            lines.append(f"- **Diet template:** {log.get('diet_template_name')}\n")
        lines.append(f"- **Diet item source:** {diet_snapshot_status(self.store, date_text)}\n")
        if log.get("weight_kg"):
            lines.append(f"- **Weight:** {log.get('weight_kg')} kg\n")
        lines.append(f"- **Checklist items eaten:** {summary['checked']} / {summary['total']}\n")
        lines.append(f"- **Checklist calories eaten:** {summary['checklist_consumed']:.0f} kcal\n")
        lines.append(f"- **Additional calories:** {summary['additional_calories']:.0f} kcal\n")
        lines.append(f"- **Total calories eaten:** {summary['consumed']:.0f} kcal\n")
        lines.append(f"- **Net calories for target after deficit adjustment:** {summary['adjusted_consumed']:.0f} kcal\n")
        lines.append(f"- **Calories remaining to target:** {summary['remaining']:.0f} kcal\n")
        lines.append(f"- **Calories over target:** {summary['over']:.0f} kcal\n")
        lines.append(f"- **Additional deficit:** {summary['additional_deficit']:.0f} kcal\n")
        lines.append(f"- **Estimated deficit today:** {summary['deficit']:.0f} kcal\n\n")

        lines.append("## Checklist\n\n")
        lines.append("| Done | Item | Calories |\n")
        lines.append("| :---: | --- | ---: |\n")
        for item in items:
            item_id = str(item.get("id", ""))
            is_checked = bool(checked.get(item_id, False))
            mark = "✓" if is_checked else ""
            name = str(item.get("name", item_id)).replace("|", "\\|")
            kcal = float(item.get("calories", 0))
            lines.append(f"| {mark} | {name} | {kcal:.2f} |\n")

        note = str(log.get("note", "")).strip()
        if note:
            lines.append("\n## Notes\n\n")
            lines.append(note + "\n")

        return "".join(lines)

    def export_selected_to_markdown(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.visible_dates):
            QMessageBox.information(self, APP_TITLE, "Select a diet history day first.")
            return

        date_text = self.visible_dates[row]
        default_path = health_report_named_path(self.store, f"DietLog_{date_text}", "md")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Extract selected diet log to Markdown",
            str(default_path),
            "Markdown Files (*.md)",
        )
        if not path:
            return
        Path(path).write_text(self.entry_to_markdown(date_text), encoding="utf-8")
        QMessageBox.information(self, APP_TITLE, f"Exported:\n{path}")

    def export_all_history(self) -> None:
        default_path = health_report_named_path(self.store, "AllDietHistory", "md")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export all diet history to Markdown",
            str(default_path),
            "Markdown Files (*.md)",
        )
        if not path:
            return

        logs = self.store.data.get("diet", {}).get("logs", {})
        parts = ["# Diet History\n\n"]

        # V2.2 export order:
        # Entry 1 should be the oldest diet day.
        # The final Entry N should be the newest/latest day.
        for idx, date_text in enumerate(sorted(logs.keys()), start=1):
            parts.append(f"<!-- Entry {idx} -->\n\n")
            parts.append(self.entry_to_markdown(date_text))
            parts.append("\n---\n\n")

        Path(path).write_text("".join(parts).rstrip() + "\n", encoding="utf-8")
        QMessageBox.information(self, APP_TITLE, f"Exported:\n{path}")


    # -----------------------------
    # Diet PDF export (V3.0)
    # -----------------------------
    def diet_dates(self) -> List[str]:
        logs = self.store.data.get("diet", {}).get("logs", {})
        return sorted_iso_dates(list(logs.keys()))

    def export_diet_pdf_all_clicked(self) -> None:
        dates = self.diet_dates()
        if not dates:
            QMessageBox.information(self, APP_TITLE, "No diet history found.")
            return
        self.export_diet_pdf_for_dates(dates, "All Dates", "AllDietHistory")

    def export_diet_pdf_last7_clicked(self) -> None:
        dates = last_n_iso_dates(self.diet_dates(), 7)
        if not dates:
            QMessageBox.information(self, APP_TITLE, "No diet history found.")
            return
        self.export_diet_pdf_for_dates(dates, f"Last 7 Dates: {dates[0]} to {dates[-1]}", "Last7DietHistory")

    def export_diet_pdf_custom_range_clicked(self) -> None:
        dates = ask_iso_date_range(self, "Export Diet PDF - Custom Range", self.diet_dates())
        if not dates:
            return
        self.export_diet_pdf_for_dates(dates, f"Custom Range: {dates[0]} to {dates[-1]}", "CustomDietHistory")

    def export_diet_pdf_for_dates(self, dates: List[str], mode_label: str, suffix: str) -> None:
        default_path = health_report_named_path(self.store, suffix, "pdf")
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Diet PDF - {mode_label}",
            str(default_path),
            "PDF Files (*.pdf)",
        )
        if not path:
            return

        try:
            body_html = self.build_diet_pdf_body(dates)
            subtitle = (
                f"Export mode: {mode_label}<br>"
                f"Source: {self.store.diet_logs_path}<br>"
                f"Dates: {', '.join(dates)}"
            )
            export_html_pdf(Path(path), "Diet History Report", subtitle, body_html, landscape=False)
            QMessageBox.information(self, APP_TITLE, f"Exported PDF:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, APP_TITLE, f"Diet PDF export failed:\n\n{exc}")

    def build_diet_pdf_body(self, dates: List[str]) -> str:
        logs = self.store.data.get("diet", {}).get("logs", {})

        parts: List[str] = []
        parts.append("<h2>Summary</h2>")
        parts.append("<p class='small'>V3.4: saved days use frozen item snapshots. Legacy unsnapped logs only show IDs that existed in that log, so new diet_config items are not injected into old dates.</p>")
        parts.append("<table class='compact'><tr><th>Date</th><th>Wt</th><th>Items</th><th>Checklist</th><th>Extra</th><th>Def adj.</th><th>Total</th><th>Target net</th><th>Est. deficit</th></tr>")
        for date_text in dates:
            summary = self.summary_for_date(date_text)
            log = logs.get(date_text, {})
            parts.append(
                "<tr>"
                f"<td>{html_escape_text(date_text)}</td>"
                f"<td class='num'>{html_escape_text(log.get('weight_kg', ''))}</td>"
                f"<td class='center'>{summary['checked']}/{summary['total']}</td>"
                f"<td class='num'>{summary['checklist_consumed']:.0f}</td>"
                f"<td class='num'>{summary['additional_calories']:.0f}</td>"
                f"<td class='num'>{summary['additional_deficit']:.0f}</td>"
                f"<td class='num'>{summary['consumed']:.0f}</td>"
                f"<td class='num'>{summary['adjusted_consumed']:.0f}</td>"
                f"<td class='num'>{summary['deficit']:.0f}</td>"
                "</tr>"
            )
        parts.append("</table>")

        for index, date_text in enumerate(dates, start=1):
            items = diet_log_items(self.store, date_text)
            log = logs.get(date_text, {})
            checked = log.get("checked", {}) if isinstance(log, dict) else {}
            summary = self.summary_for_date(date_text)
            consumed_items = [item for item in items if checked.get(str(item.get("id", "")), False)]
            skipped_count = max(0, len(items) - len(consumed_items))

            parts.append("<div class='page-break'></div>")
            parts.append(f"<h2>{html_escape_text(date_text)}</h2>")
            parts.append(f"<p class='small'>Diet item source: {html_escape_text(diet_snapshot_status(self.store, date_text))}</p>")
            parts.append("<table class='metrics'><tr><th>Weight</th><th>Items</th><th>Checklist kcal</th><th>Extra kcal</th><th>Deficit adj.</th><th>Total eaten</th><th>Target net</th><th>Est. deficit</th></tr>")
            parts.append(
                "<tr>"
                f"<td>{html_escape_text(log.get('weight_kg', '')) or '-'} kg</td>"
                f"<td>{summary['checked']} / {summary['total']}<br><span class='truncated'>{skipped_count} skipped</span></td>"
                f"<td>{summary['checklist_consumed']:.0f}</td>"
                f"<td>{summary['additional_calories']:.0f}</td>"
                f"<td>{summary['additional_deficit']:.0f}</td>"
                f"<td>{summary['consumed']:.0f}</td>"
                f"<td>{summary['adjusted_consumed']:.0f}</td>"
                f"<td>{summary['deficit']:.0f}</td>"
                "</tr>"
            )
            parts.append("</table>")

            note = stringify_value(log.get("note", "")).strip()
            if note:
                parts.append(f"<h3>Notes <span class='truncated'>(shortened in PDF)</span></h3><div class='note'>{compact_pdf_text(note, 260)}</div>")

            parts.append("<h3>Consumed checklist items</h3>")
            parts.append("<table class='diet-checklist'><tr><th style='width:62%'>Item</th><th style='width:18%'>Amount</th><th style='width:20%'>Calories</th></tr>")
            if not consumed_items:
                parts.append("<tr><td colspan='3' class='center'>No checklist items marked as eaten.</td></tr>")
            for item in consumed_items:
                item_id = str(item.get("id", ""))
                amount = f"{format_number(item.get('amount', 0), 2)} {html_escape_text(item.get('unit', ''))}".strip()
                calories = parse_float(item.get("calories", 0), 0.0)
                item_label = html_escape_text(diet_item_checklist_label(item))
                category = html_escape_text(item.get("category", ""))
                if category:
                    item_label += f"<br><span class='truncated'>{category}</span>"
                parts.append(
                    "<tr>"
                    f"<td>{item_label}</td>"
                    f"<td class='num'>{amount}</td>"
                    f"<td class='num'>{calories:.1f}</td>"
                    "</tr>"
                )
            parts.append("</table>")

        return "".join(parts)




# -----------------------------
# Food Calculator UI
# -----------------------------
class FoodCalculatorPage(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.foods: List[dict] = []

        root = QVBoxLayout(self)

        calc_box = QGroupBox("Food calorie calculator")
        calc_grid = QGridLayout(calc_box)

        self.food_combo = QComboBox()
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("amount")
        self.amount_edit.setText("100")
        self.amount_edit.setMaximumWidth(120)
        self.unit_combo = QComboBox()
        self.result_label = QLabel("—")
        self.result_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.reload_btn = QPushButton("Reload foods.json")
        self.open_btn = QPushButton("Open DATA folder")

        calc_grid.addWidget(QLabel("Food"), 0, 0)
        calc_grid.addWidget(self.food_combo, 0, 1, 1, 4)
        calc_grid.addWidget(QLabel("Amount"), 1, 0)
        calc_grid.addWidget(self.amount_edit, 1, 1)
        calc_grid.addWidget(self.unit_combo, 1, 2)
        calc_grid.addWidget(QLabel("="), 1, 3)
        calc_grid.addWidget(self.result_label, 1, 4)
        calc_grid.addWidget(self.reload_btn, 0, 5)
        calc_grid.addWidget(self.open_btn, 1, 5)
        root.addWidget(calc_box)

        help_text = QLabel(
            "Edit DATA/HealthTracker/foods.json to add foods or custom units. "
            "Unit values mean grams per unit. Example: \"medium banana\": 118."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #777777; font-size: 11px;")
        root.addWidget(help_text)

        self.foods_table = QTableWidget(0, 5)
        self.foods_table.setHorizontalHeaderLabels(["Food", "kcal / g", "kcal / 100g", "Default unit", "Available units"])
        self.foods_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.foods_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.foods_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.foods_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.foods_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.foods_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.foods_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.foods_table, 1)

        path_label = QLabel(f"Foods JSON: {self.store.foods_path}")
        path_label.setStyleSheet("color: #888888; font-size: 11px;")
        path_label.setWordWrap(True)
        root.addWidget(path_label)

        self.food_combo.currentIndexChanged.connect(self.on_food_changed)
        self.unit_combo.currentIndexChanged.connect(self.update_result)
        self.amount_edit.textChanged.connect(self.update_result)
        self.reload_btn.clicked.connect(self.reload_foods)
        self.open_btn.clicked.connect(lambda: open_folder(self.store.data_dir))
        self.foods_table.currentCellChanged.connect(self.on_table_row_changed)

        self.refresh()

    def refresh(self) -> None:
        self.foods = sorted(self.store.get_foods(), key=lambda f: str(f.get("name", "")).lower())

        self.food_combo.blockSignals(True)
        self.food_combo.clear()
        for food in self.foods:
            self.food_combo.addItem(str(food.get("name", "Food")), str(food.get("id", "")))
        self.food_combo.blockSignals(False)

        self.foods_table.setRowCount(len(self.foods))
        for row, food in enumerate(self.foods):
            kcal_g = parse_float(food.get("kcal_per_g", 0), 0.0)
            units = food.get("units", {}) if isinstance(food.get("units", {}), dict) else {}
            unit_text = ", ".join(f"{name}={format_number(grams, 2)}g" for name, grams in units.items())
            values = [
                str(food.get("name", "Food")),
                format_number(kcal_g, 3),
                format_number(kcal_g * 100.0, 1),
                str(food.get("default_unit", "g")),
                unit_text,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.foods_table.setItem(row, col, item)

        if self.foods:
            self.food_combo.setCurrentIndex(0)
            self.foods_table.setCurrentCell(0, 0)
        self.on_food_changed()

    def reload_foods(self) -> None:
        try:
            self.store.reload_foods_file()
            self.refresh()
            QMessageBox.information(self, APP_TITLE, "Reloaded foods.json.")
        except Exception as exc:
            QMessageBox.critical(self, APP_TITLE, f"Could not reload foods.json:\n\n{exc}")

    def selected_food(self) -> Optional[dict]:
        food_id = self.food_combo.currentData()
        for food in self.foods:
            if str(food.get("id", "")) == str(food_id):
                return food
        if self.foods:
            return self.foods[0]
        return None

    def on_food_changed(self) -> None:
        food = self.selected_food()
        self.unit_combo.blockSignals(True)
        self.unit_combo.clear()
        if food is not None:
            units = food.get("units", {}) if isinstance(food.get("units", {}), dict) else {"g": 1.0}
            for unit_name, grams in units.items():
                self.unit_combo.addItem(str(unit_name), float(parse_float(grams, 1.0)))
            default_unit = str(food.get("default_unit", "g"))
            idx = self.unit_combo.findText(default_unit)
            if idx >= 0:
                self.unit_combo.setCurrentIndex(idx)
        self.unit_combo.blockSignals(False)
        self.update_result()

    def on_table_row_changed(self, current_row: int, current_col: int, previous_row: int, previous_col: int) -> None:
        if 0 <= current_row < len(self.foods):
            food_id = str(self.foods[current_row].get("id", ""))
            idx = self.food_combo.findData(food_id)
            if idx >= 0 and idx != self.food_combo.currentIndex():
                self.food_combo.setCurrentIndex(idx)

    def update_result(self) -> None:
        food = self.selected_food()
        if food is None:
            self.result_label.setText("No foods loaded")
            return
        amount = parse_float(self.amount_edit.text(), 0.0)
        grams_per_unit = parse_float(self.unit_combo.currentData(), 1.0)
        grams = amount * grams_per_unit
        kcal_per_g = parse_float(food.get("kcal_per_g", 0), 0.0)
        kcal = grams * kcal_per_g
        unit_text = self.unit_combo.currentText() or "g"
        self.result_label.setText(
            f"{format_number(grams, 1)} g × {format_number(kcal_per_g, 3)} kcal/g = {format_number(kcal, 1)} kcal"
            if unit_text != "g"
            else f"{format_number(kcal, 1)} kcal"
        )


# -----------------------------
# Diet template editor
# -----------------------------
class DietTemplateEditDialog(QDialog):
    """In-app editor for a diet template (the JSON the dropdown points at).

    Mirrors RecipeEditDialog's shape. Saving writes back through
    UnifiedStore.save_diet_template, which re-validates via
    normalize_diet_config and preserves unknown fields.
    """

    ITEM_COLUMNS = ["ID", "Name", "Amount", "Unit", "Calories", "Category", "Notes"]
    KNOWN_ITEM_KEYS = {"id", "name", "amount", "unit", "calories", "category", "notes"}

    def __init__(self, parent: QWidget, template_name: str, config: Optional[dict] = None):
        super().__init__(parent)
        self.template_name = stringify_value(template_name)
        self.setWindowTitle(f"Diet template editor — {self.template_name or 'Current diet config'}")
        self.resize(900, 650)
        config = config or {}

        layout = QVBoxLayout(self)

        info_box = QGroupBox("Template summary")
        info_grid = QGridLayout(info_box)

        self.name_label = QLabel(self.template_name or "Current diet_config.json")
        self.name_label.setStyleSheet("font-weight: bold;")
        self.target_edit = QLineEdit(format_number(config.get("target_calories", 0), 2))
        self.target_edit.setPlaceholderText("Target calories")
        self.expenditure_edit = QLineEdit(format_number(config.get("estimated_expenditure", 0), 2))
        self.expenditure_edit.setPlaceholderText("Estimated expenditure")

        info_grid.addWidget(QLabel("Template"), 0, 0)
        info_grid.addWidget(self.name_label, 0, 1, 1, 3)
        info_grid.addWidget(QLabel("Target calories"), 1, 0)
        info_grid.addWidget(self.target_edit, 1, 1)
        info_grid.addWidget(QLabel("Estimated expenditure"), 1, 2)
        info_grid.addWidget(self.expenditure_edit, 1, 3)
        layout.addWidget(info_box)

        self.items_table = QTableWidget(0, len(self.ITEM_COLUMNS))
        self.items_table.setHorizontalHeaderLabels(self.ITEM_COLUMNS)
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        layout.addWidget(QLabel("Items (ID is auto-generated from the name when left blank)"))
        layout.addWidget(self.items_table, 1)

        item_buttons = QHBoxLayout()
        self.add_item_btn = QPushButton("Add item")
        self.remove_item_btn = QPushButton("Remove selected")
        self.move_up_btn = QPushButton("Move up")
        self.move_down_btn = QPushButton("Move down")
        item_buttons.addWidget(self.add_item_btn)
        item_buttons.addWidget(self.remove_item_btn)
        item_buttons.addStretch(1)
        item_buttons.addWidget(self.move_up_btn)
        item_buttons.addWidget(self.move_down_btn)
        layout.addLayout(item_buttons)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional template notes")
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setPlainText(stringify_value(config.get("notes", "")))
        layout.addWidget(QLabel("Notes"))
        layout.addWidget(self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._render_items([item for item in config.get("items", []) if isinstance(item, dict)])
        if self.items_table.rowCount() == 0:
            self.add_item_row({})

        self.add_item_btn.clicked.connect(lambda: self.add_item_row({}))
        self.remove_item_btn.clicked.connect(self.remove_selected_item)
        self.move_up_btn.clicked.connect(lambda: self.move_selected(-1))
        self.move_down_btn.clicked.connect(lambda: self.move_selected(1))

    def add_item_row(self, item: dict) -> None:
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        id_item = QTableWidgetItem(stringify_value(item.get("id", "")))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        extra = {k: v for k, v in item.items() if k not in self.KNOWN_ITEM_KEYS}
        id_item.setData(Qt.ItemDataRole.UserRole, extra)
        self.items_table.setItem(row, 0, id_item)
        values = [
            stringify_value(item.get("name", "")),
            format_number(item.get("amount", 0), 2),
            stringify_value(item.get("unit", "")),
            format_number(item.get("calories", 0), 2),
            stringify_value(item.get("category", "")) or "Other",
            stringify_value(item.get("notes", "")),
        ]
        for offset, value in enumerate(values, start=1):
            self.items_table.setItem(row, offset, QTableWidgetItem(str(value)))

    def _render_items(self, items: List[dict]) -> None:
        self.items_table.setRowCount(0)
        for item in items:
            self.add_item_row(item)

    def cell_text(self, row: int, col: int) -> str:
        item = self.items_table.item(row, col)
        return item.text().strip() if item else ""

    def _collect_rows(self) -> List[dict]:
        rows: List[dict] = []
        for row in range(self.items_table.rowCount()):
            id_item = self.items_table.item(row, 0)
            extra = id_item.data(Qt.ItemDataRole.UserRole) if id_item else {}
            if not isinstance(extra, dict):
                extra = {}
            item = dict(extra)
            item["id"] = self.cell_text(row, 0)
            item["name"] = self.cell_text(row, 1)
            item["amount"] = parse_float(self.cell_text(row, 2), 0.0)
            item["unit"] = self.cell_text(row, 3)
            item["calories"] = parse_float(self.cell_text(row, 4), 0.0)
            item["category"] = self.cell_text(row, 5) or "Other"
            notes = self.cell_text(row, 6)
            if notes or "notes" in extra:
                item["notes"] = notes
            rows.append(item)
        return rows

    def remove_selected_item(self) -> None:
        rows = sorted({index.row() for index in self.items_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.items_table.removeRow(row)

    def move_selected(self, delta: int) -> None:
        selected = sorted({index.row() for index in self.items_table.selectedIndexes()})
        if len(selected) != 1:
            return
        row = selected[0]
        target = row + delta
        if target < 0 or target >= self.items_table.rowCount():
            return
        data = self._collect_rows()
        data[row], data[target] = data[target], data[row]
        self._render_items(data)
        self.items_table.selectRow(target)

    def items(self) -> List[dict]:
        return [item for item in self._collect_rows() if stringify_value(item.get("name"))]

    def accept(self) -> None:
        if not self.items():
            QMessageBox.information(self, APP_TITLE, "Add at least one item with a name.")
            return
        super().accept()

    def get_config(self) -> dict:
        return {
            "target_calories": parse_float(self.target_edit.text(), 0.0),
            "estimated_expenditure": parse_float(self.expenditure_edit.text(), 0.0),
            "notes": self.notes_edit.toPlainText().strip(),
            "items": self.items(),
        }


# -----------------------------
# Workout template editor
# -----------------------------
class WorkoutTemplateEditDialog(QDialog):
    """In-app editor for a workout template.

    Mirrors the diet editor. Exercises are edited in a table (Name,
    Sets × Reps, Target Load, Notes) with an "Advanced (JSON)" column that
    exposes HIIT/extra fields (type, steps, rounds, step_seconds, …) as raw
    JSON so they stay visible and editable. Any unknown fields the user had
    in the JSON survive a round trip via ExerciseDef.extra.
    """

    EX_COLUMNS = ["Name", "Sets × Reps", "Target Load", "Notes", "Advanced (JSON)"]
    DISPLAY_KEYS = {"name", "sets_reps", "target_load", "notes"}

    def __init__(self, parent: QWidget, template: WorkoutTemplate):
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"Workout template editor — {template.name}")
        self.resize(960, 660)

        layout = QVBoxLayout(self)

        info_box = QGroupBox("Template summary")
        info_grid = QGridLayout(info_box)

        self.name_label = QLabel(template.name)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.rest_edit = QLineEdit(str(template.default_rest_seconds()))
        self.rest_edit.setPlaceholderText("Default rest seconds, e.g. 75")
        self.rest_edit.setMaximumWidth(100)

        info_grid.addWidget(QLabel("Template"), 0, 0)
        info_grid.addWidget(self.name_label, 0, 1)
        info_grid.addWidget(QLabel("Default rest (seconds)"), 0, 2)
        info_grid.addWidget(self.rest_edit, 0, 3)
        info_grid.setColumnStretch(1, 1)
        layout.addWidget(info_box)

        self.exercises_table = QTableWidget(0, len(self.EX_COLUMNS))
        self.exercises_table.setHorizontalHeaderLabels(self.EX_COLUMNS)
        header = self.exercises_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.exercises_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.exercises_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        layout.addWidget(QLabel("Exercises"))
        layout.addWidget(self.exercises_table, 1)

        ex_buttons = QHBoxLayout()
        self.add_ex_btn = QPushButton("Add exercise")
        self.remove_ex_btn = QPushButton("Remove selected")
        self.move_up_btn = QPushButton("Move up")
        self.move_down_btn = QPushButton("Move down")
        ex_buttons.addWidget(self.add_ex_btn)
        ex_buttons.addWidget(self.remove_ex_btn)
        ex_buttons.addStretch(1)
        ex_buttons.addWidget(self.move_up_btn)
        ex_buttons.addWidget(self.move_down_btn)
        layout.addLayout(ex_buttons)

        advanced_hint = QLabel(
            "Advanced (JSON) holds extra/HIIT fields (type, steps, rounds, step_seconds, …). "
            "Leave it as {} for a plain strength exercise."
        )
        advanced_hint.setStyleSheet("color: #888888; font-size: 11px;")
        advanced_hint.setWordWrap(True)
        layout.addWidget(advanced_hint)

        self.warmup_edit = QPlainTextEdit()
        self.warmup_edit.setPlaceholderText("Warm-up notes for this template")
        self.warmup_edit.setFixedHeight(70)
        self.warmup_edit.setPlainText(stringify_value(template.warmup_notes))
        layout.addWidget(QLabel("Warm-up notes"))
        layout.addWidget(self.warmup_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._render_exercises(template.exercises)
        if self.exercises_table.rowCount() == 0:
            self.add_exercise_row(ExerciseDef("", "", "", "", extra={}))

        self.add_ex_btn.clicked.connect(lambda: self.add_exercise_row(ExerciseDef("", "", "", "", extra={})))
        self.remove_ex_btn.clicked.connect(self.remove_selected_exercise)
        self.move_up_btn.clicked.connect(lambda: self.move_selected(-1))
        self.move_down_btn.clicked.connect(lambda: self.move_selected(1))

    def _advanced_text(self, exercise: ExerciseDef) -> str:
        extra = {k: v for k, v in exercise.extra.items() if k not in self.DISPLAY_KEYS}
        return json.dumps(extra, ensure_ascii=False) if extra else "{}"

    def add_exercise_row(self, exercise: ExerciseDef) -> None:
        row = self.exercises_table.rowCount()
        self.exercises_table.insertRow(row)
        values = [
            exercise.name,
            exercise.sets_reps,
            exercise.target_load,
            exercise.notes,
            self._advanced_text(exercise),
        ]
        for col, value in enumerate(values):
            self.exercises_table.setItem(row, col, QTableWidgetItem(stringify_value(value)))

    def _render_exercises(self, exercises: List[ExerciseDef]) -> None:
        self.exercises_table.setRowCount(0)
        for exercise in exercises:
            self.add_exercise_row(exercise)

    def cell_text(self, row: int, col: int) -> str:
        item = self.exercises_table.item(row, col)
        return item.text().strip() if item else ""

    def _parse_advanced(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text or text == "{}":
            return {}
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Advanced JSON must be an object, e.g. {\"type\": \"hiit\"}")
        return data

    def _row_to_exercise(self, row: int) -> ExerciseDef:
        extra = self._parse_advanced(self.cell_text(row, 4))
        return ExerciseDef(
            name=self.cell_text(row, 0),
            sets_reps=self.cell_text(row, 1),
            target_load=self.cell_text(row, 2),
            notes=self.cell_text(row, 3),
            extra=extra,
        )

    def remove_selected_exercise(self) -> None:
        rows = sorted({index.row() for index in self.exercises_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.exercises_table.removeRow(row)

    def move_selected(self, delta: int) -> None:
        selected = sorted({index.row() for index in self.exercises_table.selectedIndexes()})
        if len(selected) != 1:
            return
        row = selected[0]
        target = row + delta
        if target < 0 or target >= self.exercises_table.rowCount():
            return
        # Reorder using raw cell text so a malformed Advanced cell cannot block a move.
        snapshot = [
            [self.cell_text(r, c) for c in range(len(self.EX_COLUMNS))]
            for r in range(self.exercises_table.rowCount())
        ]
        snapshot[row], snapshot[target] = snapshot[target], snapshot[row]
        self.exercises_table.setRowCount(0)
        for cells in snapshot:
            r = self.exercises_table.rowCount()
            self.exercises_table.insertRow(r)
            for c, value in enumerate(cells):
                self.exercises_table.setItem(r, c, QTableWidgetItem(value))
        self.exercises_table.selectRow(target)

    def exercises(self) -> List[ExerciseDef]:
        result: List[ExerciseDef] = []
        for row in range(self.exercises_table.rowCount()):
            if not self.cell_text(row, 0):
                continue
            result.append(self._row_to_exercise(row))
        return result

    def accept(self) -> None:
        # Validate every Advanced cell so we never silently drop HIIT/extra data.
        for row in range(self.exercises_table.rowCount()):
            name = self.cell_text(row, 0)
            try:
                self._parse_advanced(self.cell_text(row, 4))
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    APP_TITLE,
                    f"Row {row + 1} ({name or 'unnamed'}) has invalid Advanced JSON:\n\n{exc}",
                )
                return
        if not self.exercises():
            QMessageBox.information(self, APP_TITLE, "Add at least one exercise with a name.")
            return
        super().accept()

    def get_template(self) -> WorkoutTemplate:
        extra = dict(self.template.extra)
        extra["_default_rest_seconds"] = parse_positive_int(self.rest_edit.text(), 75)
        return WorkoutTemplate(
            name=self.template.name,
            exercises=self.exercises(),
            warmup_notes=self.warmup_edit.toPlainText().strip(),
            extra=extra,
        )


# -----------------------------
# Recipes UI
# -----------------------------
class RecipeEditDialog(QDialog):
    def __init__(self, parent: QWidget, recipe: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Recipe editor")
        self.resize(900, 650)
        recipe = recipe or {}

        layout = QVBoxLayout(self)

        info_box = QGroupBox("Recipe summary")
        info_grid = QGridLayout(info_box)

        self.name_edit = QLineEdit(recipe.get("name", ""))
        self.name_edit.setPlaceholderText("Recipe name, e.g. Custom Boiled Lentils")
        self.total_amount_edit = QLineEdit(format_number(recipe.get("total_amount", 0), 2))
        self.total_amount_edit.setPlaceholderText("Total amount")
        self.unit_edit = QLineEdit(recipe.get("unit", "g"))
        self.unit_edit.setPlaceholderText("Unit")
        self.total_calories_edit = QLineEdit(format_number(recipe.get("total_calories", 0), 2))
        self.total_calories_edit.setPlaceholderText("Total kcal")

        info_grid.addWidget(QLabel("Name"), 0, 0)
        info_grid.addWidget(self.name_edit, 0, 1, 1, 5)
        info_grid.addWidget(QLabel("Total amount"), 1, 0)
        info_grid.addWidget(self.total_amount_edit, 1, 1)
        info_grid.addWidget(QLabel("Unit"), 1, 2)
        info_grid.addWidget(self.unit_edit, 1, 3)
        info_grid.addWidget(QLabel("Total kcal"), 1, 4)
        info_grid.addWidget(self.total_calories_edit, 1, 5)
        layout.addWidget(info_box)

        self.ingredients_table = QTableWidget(0, 4)
        self.ingredients_table.setHorizontalHeaderLabels(["Ingredient", "Amount", "Unit", "Calories"])
        self.ingredients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ingredients_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked | QTableWidget.EditTrigger.EditKeyPressed)
        layout.addWidget(QLabel("Ingredients"))
        layout.addWidget(self.ingredients_table, 1)

        ingredient_buttons = QHBoxLayout()
        self.add_ingredient_btn = QPushButton("Add ingredient")
        self.remove_ingredient_btn = QPushButton("Remove selected ingredient")
        self.recalc_btn = QPushButton("Recalculate totals from ingredients")
        ingredient_buttons.addWidget(self.add_ingredient_btn)
        ingredient_buttons.addWidget(self.remove_ingredient_btn)
        ingredient_buttons.addStretch(1)
        ingredient_buttons.addWidget(self.recalc_btn)
        layout.addLayout(ingredient_buttons)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional recipe notes")
        self.notes_edit.setFixedHeight(90)
        self.notes_edit.setPlainText(str(recipe.get("notes", "")))
        layout.addWidget(QLabel("Notes"))
        layout.addWidget(self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for ingredient in recipe.get("ingredients", []):
            self.add_ingredient_row(ingredient)
        if self.ingredients_table.rowCount() == 0:
            self.add_ingredient_row({"name": "", "amount": 0, "unit": "g", "calories": 0})

        self.add_ingredient_btn.clicked.connect(lambda: self.add_ingredient_row({"name": "", "amount": 0, "unit": "g", "calories": 0}))
        self.remove_ingredient_btn.clicked.connect(self.remove_selected_ingredient)
        self.recalc_btn.clicked.connect(self.recalculate_totals)

    def add_ingredient_row(self, ingredient: dict) -> None:
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        values = [
            ingredient.get("name", ""),
            format_number(ingredient.get("amount", 0), 2),
            ingredient.get("unit", "g"),
            format_number(ingredient.get("calories", 0), 2),
        ]
        for col, value in enumerate(values):
            self.ingredients_table.setItem(row, col, QTableWidgetItem(str(value)))

    def remove_selected_ingredient(self) -> None:
        rows = sorted({index.row() for index in self.ingredients_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.ingredients_table.removeRow(row)

    def table_text(self, row: int, col: int) -> str:
        item = self.ingredients_table.item(row, col)
        return item.text().strip() if item else ""

    def ingredients(self) -> List[dict]:
        ingredients: List[dict] = []
        for row in range(self.ingredients_table.rowCount()):
            name = self.table_text(row, 0)
            if not name:
                continue
            ingredients.append(
                {
                    "name": name,
                    "amount": parse_float(self.table_text(row, 1), 0.0),
                    "unit": self.table_text(row, 2) or "g",
                    "calories": parse_float(self.table_text(row, 3), 0.0),
                }
            )
        return ingredients

    def recalculate_totals(self) -> None:
        ingredients = self.ingredients()
        total_amount = sum(float(item.get("amount", 0) or 0) for item in ingredients)
        total_calories = sum(float(item.get("calories", 0) or 0) for item in ingredients)
        self.total_amount_edit.setText(format_number(total_amount, 2))
        self.total_calories_edit.setText(format_number(total_calories, 2))
        units = {item.get("unit", "g") for item in ingredients if item.get("unit")}
        if len(units) == 1:
            self.unit_edit.setText(next(iter(units)))

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.information(self, APP_TITLE, "Recipe name is required.")
            return
        if not self.ingredients():
            QMessageBox.information(self, APP_TITLE, "Add at least one ingredient.")
            return
        super().accept()

    def get_recipe(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "total_amount": parse_float(self.total_amount_edit.text(), 0.0),
            "unit": self.unit_edit.text().strip() or "g",
            "total_calories": parse_float(self.total_calories_edit.text(), 0.0),
            "ingredients": self.ingredients(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class RecipesPage(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.visible_recipes: List[dict] = []

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter recipes or ingredients...")
        self.refresh_btn = QPushButton("Refresh")
        top.addWidget(self.search_edit, 1)
        top.addWidget(self.refresh_btn)
        root.addLayout(top)

        splitter = QSplitter()
        self.list_widget = QListWidget()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.summary_label = QLabel("Select a recipe to view details.")
        self.summary_label.setWordWrap(True)
        self.ingredients_table = QTableWidget(0, 4)
        self.ingredients_table.setHorizontalHeaderLabels(["Ingredient", "Amount", "Unit", "Calories"])
        self.ingredients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText("Recipe notes")
        self.notes.setFixedHeight(90)
        right_layout.addWidget(self.summary_label)
        right_layout.addWidget(self.ingredients_table, 1)
        right_layout.addWidget(QLabel("Notes"))
        right_layout.addWidget(self.notes)

        splitter.addWidget(self.list_widget)
        splitter.addWidget(right_panel)
        splitter.setSizes([330, 820])
        root.addWidget(splitter, 1)

        button_row = QHBoxLayout()
        self.add_btn = QPushButton("Add recipe")
        self.edit_btn = QPushButton("Edit selected")
        self.delete_btn = QPushButton("Delete selected")
        self.restore_defaults_btn = QPushButton("Restore missing starter recipes")
        self.export_btn = QPushButton("Export recipes to Markdown")
        self.pdf_all_btn = QPushButton("PDF: All Recipes")
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.edit_btn)
        button_row.addWidget(self.delete_btn)
        button_row.addWidget(self.restore_defaults_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.pdf_all_btn)
        button_row.addWidget(self.export_btn)
        root.addLayout(button_row)

        help_text = QLabel(f"Recipes are saved separately in: {self.store.recipes_path}")
        help_text.setStyleSheet("color: #888888; font-size: 11px;")
        root.addWidget(help_text)

        self.search_edit.textChanged.connect(self.refresh)
        self.refresh_btn.clicked.connect(self.refresh)
        self.list_widget.currentRowChanged.connect(self.show_recipe_details)
        self.add_btn.clicked.connect(self.add_recipe)
        self.edit_btn.clicked.connect(self.edit_selected_recipe)
        self.delete_btn.clicked.connect(self.delete_selected_recipe)
        self.restore_defaults_btn.clicked.connect(self.restore_starter_recipes)
        self.export_btn.clicked.connect(self.export_recipes)
        self.pdf_all_btn.clicked.connect(self.export_recipes_pdf)

        self.refresh()

    def kcal_per_100g(self, recipe: dict) -> float:
        amount = parse_float(recipe.get("total_amount", 0), 0.0)
        calories = parse_float(recipe.get("total_calories", 0), 0.0)
        return (calories / amount * 100) if amount else 0.0

    def refresh(self) -> None:
        self.list_widget.clear()
        self.visible_recipes = []

        query = self.search_edit.text().strip().lower()
        recipes = self.store.get_recipes()
        for recipe in sorted(recipes, key=lambda r: str(r.get("name", "")).lower()):
            ingredients_text = " ".join(str(item.get("name", "")) for item in recipe.get("ingredients", []))
            haystack = f"{recipe.get('name', '')} {ingredients_text} {recipe.get('notes', '')}".lower()
            if query and query not in haystack:
                continue
            self.visible_recipes.append(recipe)
            amount = format_number(recipe.get("total_amount", 0), 2)
            unit = recipe.get("unit", "g")
            calories = format_number(recipe.get("total_calories", 0), 2)
            kcal_100 = format_number(self.kcal_per_100g(recipe), 2)
            self.list_widget.addItem(f"{recipe.get('name', 'Recipe')} | {amount} {unit} | {calories} kcal | {kcal_100} kcal/100g")

        if self.visible_recipes:
            self.list_widget.setCurrentRow(0)
        else:
            self.summary_label.setText("No recipes found.")
            self.ingredients_table.setRowCount(0)
            self.notes.setPlainText("")

    def show_recipe_details(self, row: int) -> None:
        if row < 0 or row >= len(self.visible_recipes):
            self.summary_label.setText("Select a recipe to view details.")
            self.ingredients_table.setRowCount(0)
            self.notes.setPlainText("")
            return

        recipe = self.visible_recipes[row]
        amount = format_number(recipe.get("total_amount", 0), 2)
        unit = recipe.get("unit", "g")
        calories = format_number(recipe.get("total_calories", 0), 2)
        kcal_100 = format_number(self.kcal_per_100g(recipe), 2)
        self.summary_label.setText(
            f"<b>{recipe.get('name', 'Recipe')}</b><br>"
            f"Total: {amount} {unit} | {calories} kcal | {kcal_100} kcal/100g"
        )

        ingredients = recipe.get("ingredients", [])
        self.ingredients_table.setRowCount(len(ingredients))
        for row_idx, ingredient in enumerate(ingredients):
            values = [
                ingredient.get("name", ""),
                format_number(ingredient.get("amount", 0), 2),
                ingredient.get("unit", "g"),
                format_number(ingredient.get("calories", 0), 2),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (1, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ingredients_table.setItem(row_idx, col, item)
        self.notes.setPlainText(str(recipe.get("notes", "")))

    def selected_recipe(self) -> Optional[dict]:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.visible_recipes):
            return None
        return self.visible_recipes[row]

    def add_recipe(self) -> None:
        dialog = RecipeEditDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.store.add_recipe(dialog.get_recipe())
        self.refresh()

    def edit_selected_recipe(self) -> None:
        recipe = self.selected_recipe()
        if recipe is None:
            QMessageBox.information(self, APP_TITLE, "Select a recipe first.")
            return
        dialog = RecipeEditDialog(self, recipe)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.store.update_recipe(recipe, dialog.get_recipe())
        self.refresh()

    def delete_selected_recipe(self) -> None:
        recipe = self.selected_recipe()
        if recipe is None:
            QMessageBox.information(self, APP_TITLE, "Select a recipe first.")
            return
        confirm = QMessageBox.question(self, APP_TITLE, f"Delete recipe '{recipe.get('name', 'Recipe')}'?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_recipe(recipe)
        self.refresh()

    def restore_starter_recipes(self) -> None:
        added = self.store.restore_starter_recipes()
        self.refresh()
        if added:
            QMessageBox.information(self, APP_TITLE, f"Restored {added} missing starter recipe/recipes.")
        else:
            QMessageBox.information(self, APP_TITLE, "All starter recipes already exist.")

    def recipe_to_markdown(self, recipe: dict) -> str:
        lines = [f"## {recipe.get('name', 'Recipe')}\n\n"]
        lines.append(f"- **Total amount:** {format_number(recipe.get('total_amount', 0), 2)} {recipe.get('unit', 'g')}\n")
        lines.append(f"- **Total calories:** {format_number(recipe.get('total_calories', 0), 2)} kcal\n")
        lines.append(f"- **Calories per 100g:** {format_number(self.kcal_per_100g(recipe), 2)} kcal\n\n")
        lines.append("| Ingredient | Amount | Unit | Calories |\n")
        lines.append("| --- | ---: | :---: | ---: |\n")
        for ingredient in recipe.get("ingredients", []):
            name = str(ingredient.get("name", "")).replace("|", "\\|")
            amount = format_number(ingredient.get("amount", 0), 2)
            unit = str(ingredient.get("unit", "g")).replace("|", "\\|")
            calories = format_number(ingredient.get("calories", 0), 2)
            lines.append(f"| {name} | {amount} | {unit} | {calories} |\n")
        notes = str(recipe.get("notes", "")).strip()
        if notes:
            lines.append(f"\nNotes: {notes}\n")
        return "".join(lines)

    def export_recipes(self) -> None:
        default_path = health_report_named_path(self.store, "AllRecipes", "md")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export recipes to Markdown",
            str(default_path),
            "Markdown Files (*.md)",
        )
        if not path:
            return
        parts = ["# Recipes\n\n"]
        for recipe in sorted(self.store.get_recipes(), key=lambda r: str(r.get("name", "")).lower()):
            parts.append(self.recipe_to_markdown(recipe))
            parts.append("\n---\n\n")
        Path(path).write_text("".join(parts).rstrip() + "\n", encoding="utf-8")
        QMessageBox.information(self, APP_TITLE, f"Exported:\n{path}")


    def export_recipes_pdf(self) -> None:
        recipes = sorted(self.store.get_recipes(), key=lambda r: str(r.get("name", "")).lower())
        if not recipes:
            QMessageBox.information(self, APP_TITLE, "No recipes found.")
            return

        default_path = health_report_named_path(self.store, "AllRecipes", "pdf")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Recipes PDF",
            str(default_path),
            "PDF Files (*.pdf)",
        )
        if not path:
            return

        try:
            body_html = self.build_recipes_pdf_body(recipes)
            subtitle = f"Export mode: All Recipes<br>Source: {self.store.recipes_path}<br>Recipes: {len(recipes)}"
            export_html_pdf(Path(path), "Recipes Report", subtitle, body_html, landscape=False)
            QMessageBox.information(self, APP_TITLE, f"Exported PDF:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, APP_TITLE, f"Recipes PDF export failed:\n\n{exc}")

    def build_recipes_pdf_body(self, recipes: List[dict]) -> str:
        parts: List[str] = []
        parts.append("<h2>Recipe Summary</h2>")
        parts.append("<table><tr><th>Recipe</th><th>Total Amount</th><th>Total Calories</th><th>Calories / 100g</th><th>Ingredients</th></tr>")
        for recipe in recipes:
            parts.append(
                "<tr>"
                f"<td>{html_escape_text(recipe.get('name', 'Recipe'))}</td>"
                f"<td class='num'>{format_number(recipe.get('total_amount', 0), 2)} {html_escape_text(recipe.get('unit', 'g'))}</td>"
                f"<td class='num'>{format_number(recipe.get('total_calories', 0), 2)}</td>"
                f"<td class='num'>{format_number(self.kcal_per_100g(recipe), 2)}</td>"
                f"<td class='num'>{len(recipe.get('ingredients', []))}</td>"
                "</tr>"
            )
        parts.append("</table>")

        for index, recipe in enumerate(recipes, start=1):
            parts.append("<div class='page-break'></div>")
            parts.append(f"<h2>{html_escape_text(recipe.get('name', 'Recipe'))}</h2>")
            parts.append("<table><tr><th>Metric</th><th>Value</th></tr>")
            parts.append(f"<tr><td>Total amount</td><td>{format_number(recipe.get('total_amount', 0), 2)} {html_escape_text(recipe.get('unit', 'g'))}</td></tr>")
            parts.append(f"<tr><td>Total calories</td><td>{format_number(recipe.get('total_calories', 0), 2)} kcal</td></tr>")
            parts.append(f"<tr><td>Calories per 100g</td><td>{format_number(self.kcal_per_100g(recipe), 2)} kcal</td></tr>")
            updated = stringify_value(recipe.get("updated_at", ""))
            if updated:
                parts.append(f"<tr><td>Updated</td><td>{html_escape_text(updated)}</td></tr>")
            parts.append("</table>")

            notes = stringify_value(recipe.get("notes", "")).strip()
            if notes:
                parts.append(f"<h3>Notes</h3><div class='note'>{html_multiline(notes)}</div>")

            parts.append("<h3>Ingredients</h3>")
            parts.append("<table><tr><th>Ingredient</th><th>Amount</th><th>Unit</th><th>Calories</th></tr>")
            for ingredient in recipe.get("ingredients", []):
                parts.append(
                    "<tr>"
                    f"<td>{html_escape_text(ingredient.get('name', ''))}</td>"
                    f"<td class='num'>{format_number(ingredient.get('amount', 0), 2)}</td>"
                    f"<td class='center'>{html_escape_text(ingredient.get('unit', 'g'))}</td>"
                    f"<td class='num'>{format_number(ingredient.get('calories', 0), 2)}</td>"
                    "</tr>"
                )
            parts.append("</table>")
        return "".join(parts)



# -----------------------------
# Workout UI
# -----------------------------
def is_hiit_exercise(exercise: ExerciseDef) -> bool:
    if exercise.exercise_type() in {"hiit", "hiit_step", "hiit_exercise"}:
        return True
    name = exercise.name.lower()
    notes = exercise.notes.lower()
    return "(hiit)" in name or "hiit" in notes


def is_explicit_hiit_block(exercise: ExerciseDef) -> bool:
    """True only for a whole HIIT/circuit block.

    V4.1 distinction:
      - type=hiit_step or type=hiit without a steps list = visible individual HIIT exercise row
      - type=hiit_block / circuit / interval_block OR a steps list = grouped timer block
    This prevents individual HIIT exercises from disappearing into one hidden timer-only block.
    """
    exercise_type = exercise.exercise_type()
    return (
        exercise_type in {"hiit_block", "circuit", "interval_block", "timer_block"}
        or isinstance(exercise.extra.get("steps"), list)
    )


def clean_hiit_name(name: str) -> str:
    return re.sub(r"\s*\(\s*hiit\s*\)\s*", "", stringify_value(name), flags=re.IGNORECASE).strip()


def step_name_and_seconds(raw_step: Any, default_seconds: int) -> Tuple[str, int]:
    if isinstance(raw_step, dict):
        name = first_nonempty_string(raw_step.get("name"), raw_step.get("exercise"), raw_step.get("title"), raw_step.get("movement"), "HIIT step")
        seconds = parse_positive_int(first_present(raw_step, "seconds", "duration_seconds", "duration", "time"), default_seconds)
        return name, seconds
    return stringify_value(raw_step) or "HIIT step", default_seconds


def fallback_hiit_round_rest(group: List[ExerciseDef], default: int = 15) -> int:
    for exercise in group:
        rest = parse_positive_int(exercise.field("between_round_rest_seconds", "round_rest_seconds", "rest_seconds", default=""), -1)
        if rest >= 0:
            return rest
        m = re.search(r"rest\s+(\d+)\s*(?:seconds?|secs?|s)\b", exercise.notes.lower())
        if m:
            return int(m.group(1))
    return default


def explicit_hiit_steps(exercise: ExerciseDef) -> List[Dict[str, Any]]:
    rounds = parse_positive_int(exercise.field("rounds", "repeat", "repeats", default=""), parse_sets_count(exercise.sets_reps, 3))
    default_seconds = parse_positive_int(
        exercise.field("step_seconds", "seconds", "duration_seconds", "duration", default=""),
        parse_seconds_from_text(exercise.sets_reps, 30),
    )
    between_round_rest = parse_positive_int(
        exercise.field("between_round_rest_seconds", "round_rest_seconds", "rest_between_rounds", default=""),
        15,
    )
    raw_steps = exercise.extra.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raw_steps = [clean_hiit_name(exercise.name)]

    steps: List[Dict[str, Any]] = []
    for round_index in range(1, rounds + 1):
        for raw_step in raw_steps:
            step_name, seconds = step_name_and_seconds(raw_step, default_seconds)
            steps.append({
                "kind": "timed",
                "mode": "hiit",
                "label": f"{exercise.name}\nRound {round_index}/{rounds}\n{step_name}",
                "duration": seconds,
                "notes": exercise.notes,
            })
        if round_index < rounds and between_round_rest > 0:
            steps.append({
                "kind": "timed",
                "mode": "rest",
                "label": f"HIIT Rest\nNext round {round_index + 1}/{rounds}",
                "duration": between_round_rest,
                "notes": "Short HIIT round break.",
            })
    return steps


def fallback_hiit_group_steps(group: List[ExerciseDef]) -> List[Dict[str, Any]]:
    if not group:
        return []
    rounds = max(parse_sets_count(ex.sets_reps, 3) for ex in group)
    between_round_rest = fallback_hiit_round_rest(group, 15)
    steps: List[Dict[str, Any]] = []
    for round_index in range(1, rounds + 1):
        for exercise in group:
            seconds = parse_seconds_from_text(exercise.sets_reps, 30)
            steps.append({
                "kind": "timed",
                "mode": "hiit",
                "label": f"HIIT Finisher\nRound {round_index}/{rounds}\n{clean_hiit_name(exercise.name)}",
                "duration": seconds,
                "notes": exercise.notes,
            })
        if round_index < rounds and between_round_rest > 0:
            steps.append({
                "kind": "timed",
                "mode": "rest",
                "label": f"HIIT Rest\nNext round {round_index + 1}/{rounds}",
                "duration": between_round_rest,
                "notes": "Short HIIT round break.",
            })
    return steps


def build_workout_timer_plan(template: WorkoutTemplate) -> List[Dict[str, Any]]:
    """
    V4.0 JSON-driven timer plan.

    Normal exercises become manual set prompts plus rest timers.
    HIIT blocks auto-run timed steps.
    The timer is intentionally generated from workout_templates.json metadata,
    not from hardcoded exercise names.
    """
    plan: List[Dict[str, Any]] = []
    default_rest = template.default_rest_seconds()
    exercises = list(template.exercises)
    i = 0
    while i < len(exercises):
        exercise = exercises[i]

        if is_explicit_hiit_block(exercise):
            plan.extend(explicit_hiit_steps(exercise))
            i += 1
            continue

        if is_hiit_exercise(exercise):
            group: List[ExerciseDef] = []
            while i < len(exercises) and is_hiit_exercise(exercises[i]) and not is_explicit_hiit_block(exercises[i]):
                group.append(exercises[i])
                i += 1
            plan.extend(fallback_hiit_group_steps(group))
            continue

        sets = parse_positive_int(exercise.field("sets", "set_count", "setCount", default=""), parse_sets_count(exercise.sets_reps, 1))
        rest_seconds = parse_positive_int(exercise.field("rest_seconds", "rest", default=""), default_rest)
        for set_index in range(1, sets + 1):
            plan.append({
                "kind": "manual",
                "mode": "strength",
                "label": f"{exercise.name}\nSet {set_index}/{sets}",
                "duration": 0,
                "notes": f"{exercise.sets_reps}\n{exercise.target_load}\n{exercise.notes}".strip(),
            })
            if rest_seconds > 0:
                plan.append({
                    "kind": "timed",
                    "mode": "rest",
                    "label": f"Rest\n{rest_seconds} seconds",
                    "duration": rest_seconds,
                    "notes": f"Next: {exercise.name if set_index < sets else 'next exercise'}",
                })
        i += 1

    # Remove final strength rest when it is the last generated step. HIIT round rests
    # are kept because they are inside the HIIT block logic.
    while plan and plan[-1].get("mode") == "rest" and stringify_value(plan[-1].get("notes")).startswith("Next: next exercise"):
        plan.pop()
    return plan



def build_workout_hiit_timer_plan(template: WorkoutTemplate) -> List[Dict[str, Any]]:
    """Build only the HIIT portion of a workout template.

    Normal strength exercises stay in the main tracker; this timer is only for
    automatic timed HIIT blocks/steps.
    """
    plan: List[Dict[str, Any]] = []
    exercises = list(template.exercises)
    i = 0
    while i < len(exercises):
        exercise = exercises[i]

        if is_explicit_hiit_block(exercise):
            plan.extend(explicit_hiit_steps(exercise))
            i += 1
            continue

        if is_hiit_exercise(exercise):
            group: List[ExerciseDef] = []
            while i < len(exercises) and is_hiit_exercise(exercises[i]) and not is_explicit_hiit_block(exercises[i]):
                group.append(exercises[i])
                i += 1
            plan.extend(fallback_hiit_group_steps(group))
            continue

        i += 1

    return plan


def build_workout_rest_timer_plan(template: WorkoutTemplate) -> List[Dict[str, Any]]:
    """One reusable manual-workout rest timer step.

    This intentionally does not walk through every strength exercise. The main
    workout tab already handles exercise names, loads, and RIR. This timer only
    measures the user's standard rest interval.
    """
    rest_seconds = template.default_rest_seconds()
    return [{
        "kind": "timed",
        "mode": "rest",
        "label": f"Manual Workout Rest\n{rest_seconds} seconds",
        "duration": rest_seconds,
        "notes": "Use this between normal strength sets. Press Start Rest to repeat after it finishes.",
    }]


class WorkoutTimerDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], template: WorkoutTemplate, timer_mode: str = "hiit"):
        super().__init__(parent)
        self.template = template
        self.timer_mode = timer_mode
        if timer_mode == "rest":
            self.steps = build_workout_rest_timer_plan(template)
        elif timer_mode == "full":
            self.steps = build_workout_timer_plan(template)
        else:
            self.steps = build_workout_hiit_timer_plan(template)
        self.current_index = -1
        self.remaining = 0
        self.running = False
        self.paused = False

        self.setWindowTitle(f"{timer_mode.upper()} Timer - {template.name}")
        self.resize(900, 650)
        self.installEventFilter(self)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #eeeeee; }
            QLabel { color: #eeeeee; }
            QPushButton {
                background-color: #1f1f1f;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #333333; }
            QPlainTextEdit {
                background-color: #1a1a1a;
                color: #dddddd;
                border: 1px solid #444444;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.progress_label = QLabel("Ready")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setFont(QFont("Arial", 18))
        layout.addWidget(self.progress_label)

        self.exercise_label = QLabel("Press Start")
        self.exercise_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.exercise_label.setWordWrap(True)
        self.exercise_label.setFont(QFont("Arial", 42))
        layout.addWidget(self.exercise_label, 1)

        self.timer_label = QLabel("")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setFont(QFont("Arial", 74))
        layout.addWidget(self.timer_label)

        self.notes_box = QPlainTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setMaximumHeight(120)
        layout.addWidget(self.notes_box)

        row = QHBoxLayout()
        self.start_next_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.back_btn = QPushButton("Back")
        self.skip_btn = QPushButton("Skip")
        self.stop_btn = QPushButton("Stop")
        self.pause_btn.setEnabled(False)
        self.back_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        row.addWidget(self.start_next_btn)
        row.addWidget(self.pause_btn)
        row.addWidget(self.back_btn)
        row.addWidget(self.skip_btn)
        row.addWidget(self.stop_btn)
        layout.addLayout(row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

        self.beep_sound = make_beep_sound(self)

        self.start_next_btn.clicked.connect(self.start_or_next)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.back_btn.clicked.connect(self.previous_step)
        self.skip_btn.clicked.connect(self.next_step)
        self.stop_btn.clicked.connect(self.reject)

        if not self.steps:
            self.exercise_label.setText("No HIIT timer steps found in this template.")
            self.start_next_btn.setEnabled(False)
            self.notes_box.setPlainText("Add HIIT entries to workout_templates.json, for example type=hiit_step or names containing (HIIT).")

    def beep(self) -> None:
        play_beep(self.beep_sound)

    def current_step(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.current_index < len(self.steps):
            return self.steps[self.current_index]
        return None

    def start_or_next(self) -> None:
        step = self.current_step()
        if step is not None and step.get("kind") == "manual":
            self.next_step()
            return
        if self.current_index < 0:
            self.next_step()

    def previous_step(self) -> None:
        if self.current_index <= 0:
            return
        self.current_index -= 2
        self.next_step()

    def next_step(self) -> None:
        self.timer.stop()
        self.paused = False
        self.pause_btn.setText("Pause")
        self.current_index += 1
        if self.current_index >= len(self.steps):
            self.finish_workout()
            return

        step = self.steps[self.current_index]
        self.remaining = int(step.get("duration", 0) or 0)
        self.show_step(step)
        self.beep()

        self.back_btn.setEnabled(self.current_index > 0)
        self.skip_btn.setEnabled(True)
        self.pause_btn.setEnabled(step.get("kind") == "timed")

        if step.get("kind") == "timed":
            self.running = True
            self.timer.start(1000)
        else:
            self.running = False
            self.timer.stop()

    def show_step(self, step: Dict[str, Any]) -> None:
        self.progress_label.setText(f"Step {self.current_index + 1} / {len(self.steps)}")
        self.exercise_label.setText(html.escape(stringify_value(step.get("label", ""))).replace("\n", "<br>"))
        self.notes_box.setPlainText(stringify_value(step.get("notes", "")))
        if step.get("kind") == "manual":
            self.timer_label.setText("Manual")
            self.start_next_btn.setText("Next / Start Rest")
        else:
            self.timer_label.setText(f"{self.remaining}s")
            self.start_next_btn.setText("Running")

    def tick(self) -> None:
        if self.paused:
            return
        step = self.current_step()
        if step is None:
            return
        self.timer_label.setText(f"{self.remaining}s")
        self.remaining -= 1
        if self.remaining < 0:
            self.next_step()

    def toggle_pause(self) -> None:
        if self.current_step() is None or self.current_step().get("kind") != "timed":
            return
        self.paused = not self.paused
        if self.paused:
            self.timer.stop()
            self.pause_btn.setText("Resume")
        else:
            self.timer.start(1000)
            self.pause_btn.setText("Pause")

    def finish_workout(self) -> None:
        self.timer.stop()
        self.running = False
        self.progress_label.setText("Complete")
        if self.timer_mode == "rest":
            self.exercise_label.setText("Rest Complete")
            self.notes_box.setPlainText("Press Start Rest to run another rest timer.")
            self.current_index = -1
            self.start_next_btn.setText("Start Rest")
            self.start_next_btn.setEnabled(True)
        else:
            self.exercise_label.setText("HIIT Timer Complete")
            self.notes_box.setPlainText("Timer finished. You can now mark the HIIT rows done and save the workout entry in the main tracker.")
            self.start_next_btn.setEnabled(False)
        self.timer_label.setText("✓")
        self.pause_btn.setEnabled(False)
        self.back_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.beep()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return True
        return super().eventFilter(source, event)


class ExerciseRow(QWidget):
    def __init__(self, exercise: ExerciseDef, saved: Optional[dict] = None):
        super().__init__()
        self.exercise = exercise
        saved = saved or {}

        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(6)

        self.done_cb = QCheckBox()
        self.done_cb.setChecked(bool(saved.get("done", False)))

        display_name = exercise.name
        if is_explicit_hiit_block(exercise):
            display_name = f"{exercise.name} [HIIT timer block]"
        elif is_hiit_exercise(exercise):
            display_name = f"{exercise.name} [HIIT]"
        name_label = QLabel(display_name)
        name_label.setMinimumWidth(220)
        name_label.setWordWrap(True)

        self.sets_reps_edit = QLineEdit(saved.get("sets_reps", exercise.sets_reps))
        self.load_edit = QLineEdit(saved.get("target_load", exercise.target_load))
        self.rir_edit = QLineEdit(saved.get("rir", ""))
        self.notes_edit = QLineEdit(first_nonempty_string(saved.get("notes"), exercise.notes))
        self.notes_edit.setReadOnly(True)

        self.sets_reps_edit.setPlaceholderText("Sets × Reps")
        self.load_edit.setPlaceholderText("Target load")
        self.rir_edit.setPlaceholderText("RIR after sets")
        self.notes_edit.setPlaceholderText("Exercise notes from template")

        if is_hiit_exercise(exercise) or is_explicit_hiit_block(exercise):
            self.rir_edit.setPlaceholderText("No RIR for HIIT")
            self.rir_edit.setEnabled(False)

        layout.addWidget(self.done_cb, 0, 0)
        layout.addWidget(name_label, 0, 1)
        layout.addWidget(QLabel("Sets × Reps"), 0, 2)
        layout.addWidget(self.sets_reps_edit, 0, 3)
        layout.addWidget(QLabel("Load"), 0, 4)
        layout.addWidget(self.load_edit, 0, 5)
        layout.addWidget(QLabel("RIR"), 1, 2)
        layout.addWidget(self.rir_edit, 1, 3)
        layout.addWidget(QLabel("Notes"), 1, 4)
        layout.addWidget(self.notes_edit, 1, 5)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(5, 1)

    def current_exercise_def(self) -> ExerciseDef:
        return ExerciseDef(
            self.exercise.name,
            self.sets_reps_edit.text().strip(),
            self.load_edit.text().strip(),
            self.notes_edit.text().strip(),
            extra=dict(self.exercise.extra),
        )

    def to_dict(self) -> dict:
        data = dict(self.exercise.extra)
        data.update({
            "name": self.exercise.name,
            "done": self.done_cb.isChecked(),
            "sets_reps": self.sets_reps_edit.text().strip(),
            "target_load": self.load_edit.text().strip(),
            "rir": self.rir_edit.text().strip(),
            "notes": self.notes_edit.text().strip(),
        })
        return data


class WorkoutBuilder(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.rows: List[ExerciseRow] = []
        self.templates: Dict[str, WorkoutTemplate] = {}
        self.current_template_extra: Dict[str, Any] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        header_box = QGroupBox("Log workout")
        header_layout = QGridLayout(header_box)

        self.template_combo = QComboBox()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        # Tracks the date our code last wrote into the picker. Lets us bump to
        # "today" on tab activation only when the user hasn't manually picked
        # a different date — see refresh_today_if_stale().
        self._last_app_set_date = self.date_edit.date()

        self.warmup_notes = QPlainTextEdit()
        self.warmup_notes.setReadOnly(True)
        self.warmup_notes.setPlaceholderText("Warm-up notes from template")
        self.warmup_notes.setFixedHeight(90)

        self.progress_label = QLabel("0 / 0 completed")

        self.edit_template_btn = QPushButton("Edit template…")
        self.edit_template_btn.setToolTip("Edit this workout template's exercises and rest. Saved workout history keeps its own snapshots.")
        self.manage_template_btn = QPushButton("Manage ▾")
        self.manage_template_btn.setToolTip("Create, rename, or delete workout templates.")
        manage_menu = QMenu(self.manage_template_btn)
        self.new_template_action = manage_menu.addAction("New template…")
        self.rename_template_action = manage_menu.addAction("Rename template…")
        self.delete_template_action = manage_menu.addAction("Delete template…")
        self.manage_template_btn.setMenu(manage_menu)

        header_layout.addWidget(QLabel("Template"), 0, 0)
        header_layout.addWidget(self.template_combo, 0, 1)
        header_layout.addWidget(QLabel("Date"), 0, 2)
        header_layout.addWidget(self.date_edit, 0, 3)
        header_layout.addWidget(self.progress_label, 0, 4)
        header_layout.addWidget(self.edit_template_btn, 0, 5)
        header_layout.addWidget(self.manage_template_btn, 0, 6)
        header_layout.addWidget(QLabel("Warm-up Notes"), 1, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(self.warmup_notes, 1, 1, 1, 4)
        outer.addWidget(header_box)

        self.scroll_widget = QWidget()
        self.rows_layout = QVBoxLayout(self.scroll_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.scroll_widget)
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        self.mark_all_btn = QPushButton("Mark all done")
        self.clear_checks_btn = QPushButton("Clear checks")
        self.reset_template_btn = QPushButton("Reset today's fields")
        self.start_hiit_timer_btn = QPushButton("Start HIIT Timer")

        # V4.3: keep the normal-strength rest timer inside the Workout Log tab.
        # The full timer dialog is still used for HIIT, but 75s rest timing should
        # not steal screen space from the exercise/RIR list.
        self.rest_timer_label = QLabel("Rest: 75s")
        self.rest_timer_label.setMinimumWidth(90)
        self.rest_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rest_timer_label.setStyleSheet("font-weight: bold;")
        self.start_rest_timer_btn = QPushButton("Start Rest")
        self.pause_rest_timer_btn = QPushButton("Pause")
        self.reset_rest_timer_btn = QPushButton("Reset")
        self.pause_rest_timer_btn.setEnabled(False)

        buttons.addWidget(self.mark_all_btn)
        buttons.addWidget(self.clear_checks_btn)
        buttons.addWidget(self.reset_template_btn)
        buttons.addWidget(self.start_hiit_timer_btn)
        buttons.addSpacing(18)
        buttons.addWidget(QLabel("Rest Timer:"))
        buttons.addWidget(self.rest_timer_label)
        buttons.addWidget(self.start_rest_timer_btn)
        buttons.addWidget(self.pause_rest_timer_btn)
        buttons.addWidget(self.reset_rest_timer_btn)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self.rest_timer = QTimer(self)
        self.rest_timer.timeout.connect(self.tick_rest_timer)
        self.rest_remaining = 0
        self.rest_running = False
        self.rest_paused = False
        self.embedded_beep_sound = make_beep_sound(self)

        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        self.edit_template_btn.clicked.connect(self.edit_selected_template)
        self.new_template_action.triggered.connect(self.new_workout_template)
        self.rename_template_action.triggered.connect(self.rename_selected_workout_template)
        self.delete_template_action.triggered.connect(self.delete_selected_workout_template)
        self.mark_all_btn.clicked.connect(self.mark_all_done)
        self.clear_checks_btn.clicked.connect(self.clear_checks)
        self.reset_template_btn.clicked.connect(self.reset_fields)
        self.start_hiit_timer_btn.clicked.connect(self.start_hiit_timer)
        self.start_rest_timer_btn.clicked.connect(self.start_rest_timer)
        self.pause_rest_timer_btn.clicked.connect(self.toggle_rest_pause)
        self.reset_rest_timer_btn.clicked.connect(self.reset_rest_timer)

        self.refresh_templates()

    def refresh_templates(self) -> None:
        self.templates = self.store.get_templates()

        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItems(list(self.templates.keys()))
        last = self.store.get_last_template()
        if last in self.templates:
            self.template_combo.setCurrentText(last)
        self.template_combo.blockSignals(False)

        has_templates = bool(self.templates)
        self.template_combo.setEnabled(has_templates)
        self.mark_all_btn.setEnabled(has_templates)
        self.clear_checks_btn.setEnabled(has_templates)
        self.reset_template_btn.setEnabled(has_templates)
        self.start_hiit_timer_btn.setEnabled(has_templates)
        self.start_rest_timer_btn.setEnabled(has_templates)
        self.reset_rest_timer_btn.setEnabled(has_templates)
        self.edit_template_btn.setEnabled(has_templates)
        self.pause_rest_timer_btn.setEnabled(False)
        self.reset_rest_timer()

        if has_templates:
            self.build_template(self.template_combo.currentText())
        else:
            self.clear_rows()
            label = QLabel(
                "No workout templates yet.\n\n"
                "Create your first one to start logging workouts — no JSON editing required."
            )
            label.setWordWrap(True)
            label.setStyleSheet("font-size: 14px; margin-top: 16px;")
            self.rows_layout.addWidget(label)
            create_btn = QPushButton("Create your first template →")
            create_btn.setToolTip("Create a new workout template and open the editor.")
            create_btn.clicked.connect(self.new_workout_template)
            self.rows_layout.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignLeft)
            power_user = QLabel(
                "Power users can also add templates directly to "
                "DATA/HealthTracker/WorkoutTracker/workout_templates.json (File → Open data folder)."
            )
            power_user.setWordWrap(True)
            power_user.setStyleSheet("color: #888888; font-size: 11px; margin-top: 6px;")
            self.rows_layout.addWidget(power_user)
            self.rows_layout.addStretch(1)
            self.update_progress()

    def edit_selected_template(self) -> None:
        name = self.template_combo.currentText()
        if name not in self.templates:
            QMessageBox.information(self, APP_TITLE, "Select a workout template first.")
            return

        dialog = WorkoutTemplateEditDialog(self, self.templates[name])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            updated = self.templates.copy()
            updated[name] = dialog.get_template()
            self.store.set_templates(updated)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, f"Could not save the workout template.\n\n{exc}")
            return

        # Reload from disk and rebuild the visible builder. Saved workout-history
        # entries carry their own exercise snapshots, so editing a template never
        # rewrites logged workouts.
        self.refresh_templates()
        self.template_combo.setCurrentText(name)
        QMessageBox.information(
            self,
            APP_TITLE,
            "Workout template saved. Logged workouts keep their saved snapshots.",
        )

    def new_workout_template(self) -> None:
        name, ok = QInputDialog.getText(self, APP_TITLE, "Name for the new workout template:")
        if not ok or not stringify_value(name):
            return
        try:
            display = self.store.create_workout_template(name)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return

        self.refresh_templates()
        self.template_combo.setCurrentText(display)
        # Open the editor immediately so the user fills the empty template.
        if display in self.templates:
            dialog = WorkoutTemplateEditDialog(self, self.templates[display])
            if dialog.exec() == QDialog.DialogCode.Accepted:
                try:
                    updated = self.store.get_templates()
                    updated[display] = dialog.get_template()
                    self.store.set_templates(updated)
                except Exception as exc:
                    QMessageBox.warning(self, APP_TITLE, f"Could not save the workout template.\n\n{exc}")
            self.refresh_templates()
            self.template_combo.setCurrentText(display)

    def rename_selected_workout_template(self) -> None:
        old = self.template_combo.currentText()
        if old not in self.templates:
            QMessageBox.information(self, APP_TITLE, "Select a workout template first.")
            return
        new, ok = QInputDialog.getText(self, APP_TITLE, "New name for this workout template:", text=old)
        if not ok or not stringify_value(new):
            return
        try:
            display = self.store.rename_workout_template(old, new)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return
        self.refresh_templates()
        self.template_combo.setCurrentText(display)

    def delete_selected_workout_template(self) -> None:
        target = self.template_combo.currentText()
        if target not in self.templates:
            QMessageBox.information(self, APP_TITLE, "Select a workout template first.")
            return
        confirm = QMessageBox.question(
            self, APP_TITLE,
            f"Delete workout template '{target}'?\n\nLogged workouts that used it keep their saved snapshots.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_workout_template(target)
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return
        self.refresh_templates()

    def clear_rows(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.rows = []

    def set_warmup_text(self, text: str) -> None:
        self.warmup_notes.setPlainText((text or "").strip())

    def build_template(self, template_name: str, saved_entry: Optional[dict] = None) -> None:
        self.clear_rows()
        self.current_template_extra = {}

        # Per-row saved state (done/rir/etc.); populated only when editing a
        # saved history entry so Edit actually restores the previous values
        # instead of dropping them — was "delete and re-enter" before this.
        saved_rows: List[Optional[dict]] = []

        # V4.0 safety rule: when editing an old workout history entry, load its
        # saved exercise snapshot first. Do not rebuild it from the current template.
        if saved_entry and saved_entry.get("exercises"):
            raw_exercises = saved_entry.get("exercises", [])
            exercises = [
                normalize_exercise_definition(ex, fallback_name=f"Exercise {index}")
                for index, ex in enumerate(raw_exercises, start=1)
            ]
            saved_rows = [ex if isinstance(ex, dict) else None for ex in raw_exercises]
            self.set_warmup_text(saved_entry.get("warmup_notes", saved_entry.get("workout_notes", "")))
            self.current_template_extra = {
                "_default_rest_seconds": saved_entry.get("default_rest_seconds", 75),
            }
            if template_name in self.templates:
                notice = QLabel("Loaded the saved workout-history snapshot, not the current template. This protects old logs from template edits.")
                notice.setWordWrap(True)
                self.rows_layout.addWidget(notice)
            else:
                notice = QLabel("This entry's original template is not loaded. The saved exercise list was loaded instead.")
                notice.setWordWrap(True)
                self.rows_layout.addWidget(notice)
        elif template_name in self.templates:
            template = self.templates[template_name]
            exercises = template.exercises
            saved_rows = [None] * len(exercises)
            self.current_template_extra = dict(template.extra)
            self.set_warmup_text(template.warmup_notes)
        else:
            self.set_warmup_text("")
            empty = QLabel("No exercises to show.")
            self.rows_layout.addWidget(empty)
            self.rows_layout.addStretch(1)
            self.update_progress()
            return

        for index, exercise in enumerate(exercises):
            saved = saved_rows[index] if index < len(saved_rows) else None
            row = ExerciseRow(exercise, saved)
            row.done_cb.toggled.connect(self.update_progress)
            self.rows.append(row)
            self.rows_layout.addWidget(row)

        self.rows_layout.addStretch(1)
        self.update_progress()

    def _on_template_changed(self, template_name: str) -> None:
        if template_name:
            self.store.set_last_template(template_name)
        self.build_template(template_name)
        self.reset_rest_timer()

    def update_progress(self) -> None:
        total = len(self.rows)
        done = sum(1 for row in self.rows if row.done_cb.isChecked())
        self.progress_label.setText(f"{done} / {total} completed")

    def mark_all_done(self) -> None:
        for row in self.rows:
            row.done_cb.setChecked(True)
        self.update_progress()

    def clear_checks(self) -> None:
        for row in self.rows:
            row.done_cb.setChecked(False)
        self.update_progress()

    def reset_fields(self) -> None:
        current = self.template_combo.currentText()
        self._last_app_set_date = QDate.currentDate()
        self.date_edit.setDate(self._last_app_set_date)
        self.build_template(current)

    def refresh_today_if_stale(self) -> None:
        """Bump the date picker to today when the app has been left open across
        midnight. Only fires if the user hasn't manually picked a different
        date (the picker still matches the value we last set) — so people
        editing a past date aren't yanked forward."""
        today = QDate.currentDate()
        if self._last_app_set_date < today and self.date_edit.date() == self._last_app_set_date:
            self._last_app_set_date = today
            self.date_edit.setDate(today)
            self.build_template(self.template_combo.currentText())

    def current_timer_template(self) -> WorkoutTemplate:
        return WorkoutTemplate(
            name=self.template_combo.currentText() or "Workout",
            exercises=[row.current_exercise_def() for row in self.rows],
            warmup_notes=self.warmup_notes.toPlainText().strip(),
            extra=dict(self.current_template_extra),
        )

    def start_hiit_timer(self) -> None:
        template = self.current_timer_template()
        if not template.exercises:
            QMessageBox.information(self, APP_TITLE, "No exercises are available for the HIIT timer.")
            return
        if not build_workout_hiit_timer_plan(template):
            QMessageBox.information(self, APP_TITLE, "No HIIT exercises found in this template. Add type=hiit_step or '(HIIT)' entries to workout_templates.json.")
            return
        dialog = WorkoutTimerDialog(self, template, timer_mode="hiit")
        dialog.exec()

    def current_rest_seconds(self) -> int:
        try:
            return max(1, int(self.current_timer_template().default_rest_seconds()))
        except Exception:
            return 75

    def format_rest_time(self, seconds: int) -> str:
        seconds = max(0, int(seconds))
        minutes, sec = divmod(seconds, 60)
        if minutes:
            return f"{minutes}:{sec:02d}"
        return f"{sec}s"

    def update_rest_timer_label(self) -> None:
        if self.rest_running or self.rest_remaining > 0:
            self.rest_timer_label.setText(f"Rest: {self.format_rest_time(self.rest_remaining)}")
        else:
            self.rest_timer_label.setText(f"Rest: {self.current_rest_seconds()}s")

    def embedded_beep(self) -> None:
        play_beep(self.embedded_beep_sound)

    def start_rest_timer(self) -> None:
        """Start/restart the compact in-tab rest timer."""
        self.rest_timer.stop()
        self.rest_remaining = self.current_rest_seconds()
        self.rest_running = True
        self.rest_paused = False
        self.start_rest_timer_btn.setText("Restart Rest")
        self.pause_rest_timer_btn.setText("Pause")
        self.pause_rest_timer_btn.setEnabled(True)
        self.update_rest_timer_label()
        self.embedded_beep()
        self.rest_timer.start(1000)

    def tick_rest_timer(self) -> None:
        if self.rest_paused:
            return
        if self.rest_remaining <= 1:
            self.rest_remaining = 0
            self.rest_timer.stop()
            self.rest_running = False
            self.rest_paused = False
            self.rest_timer_label.setText("Rest: ✓")
            self.start_rest_timer_btn.setText("Start Rest")
            self.pause_rest_timer_btn.setText("Pause")
            self.pause_rest_timer_btn.setEnabled(False)
            self.embedded_beep()
            return
        self.rest_remaining -= 1
        self.update_rest_timer_label()

    def toggle_rest_pause(self) -> None:
        if not self.rest_running:
            return
        self.rest_paused = not self.rest_paused
        if self.rest_paused:
            self.rest_timer.stop()
            self.pause_rest_timer_btn.setText("Resume")
        else:
            self.rest_timer.start(1000)
            self.pause_rest_timer_btn.setText("Pause")

    def reset_rest_timer(self) -> None:
        if not hasattr(self, "rest_timer"):
            return
        self.rest_timer.stop()
        self.rest_remaining = 0
        self.rest_running = False
        self.rest_paused = False
        self.start_rest_timer_btn.setText("Start Rest")
        self.pause_rest_timer_btn.setText("Pause")
        self.pause_rest_timer_btn.setEnabled(False)
        self.update_rest_timer_label()

    def get_entry(self) -> dict:
        return {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "template": self.template_combo.currentText(),
            "warmup_notes": self.warmup_notes.toPlainText().strip(),
            "default_rest_seconds": parse_positive_int(first_present(self.current_template_extra, "_default_rest_seconds", "default_rest_seconds", "rest_seconds"), 75),
            "exercises": [row.to_dict() for row in self.rows],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def load_entry(self, entry: dict) -> None:
        template = entry.get("template", next(iter(self.templates), ""))
        self.template_combo.blockSignals(True)
        if template not in self.templates and self.template_combo.findText(template) == -1:
            self.template_combo.addItem(template)
        self.template_combo.setCurrentText(template)
        self.template_combo.blockSignals(False)

        try:
            loaded_date = datetime.strptime(entry.get("date", date.today().isoformat()), "%Y-%m-%d").date()
            self.date_edit.setDate(QDate(loaded_date.year, loaded_date.month, loaded_date.day))
        except ValueError:
            self.date_edit.setDate(QDate.currentDate())

        self.build_template(template, entry)


class WorkoutLogPage(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        self.builder = WorkoutBuilder(store)
        root.addWidget(self.builder, 1)

        save_row = QHBoxLayout()
        self.save_btn = QPushButton("Save workout entry")
        save_row.addStretch(1)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

        self.save_btn.clicked.connect(self.save_workout)

    def refresh_templates(self) -> None:
        self.builder.refresh_templates()

    def save_workout(self) -> None:
        if not self.builder.templates:
            QMessageBox.warning(self, APP_TITLE, "No workout templates are loaded, so there is nothing to save.")
            return
        entry = self.builder.get_entry()
        self.store.add_workout_entry(entry)
        QMessageBox.information(self, APP_TITLE, f"Workout saved for {entry['date']}.")


class EntryEditorDialog(QDialog):
    def __init__(self, parent: QWidget, store: UnifiedStore, entry: dict):
        super().__init__(parent)
        self.setWindowTitle("Edit workout entry")
        self.resize(980, 760)

        self.builder = WorkoutBuilder(store)
        self.builder.load_entry(entry)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.builder)
        layout.addWidget(buttons)

    def get_updated_entry(self) -> dict:
        return self.builder.get_entry()


class WorkoutHistoryPage(QWidget):
    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.visible_entries: List[dict] = []

        layout = QVBoxLayout(self)
        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by date, template, note, or exercise...")
        self.completed_filter = QComboBox()
        self.completed_filter.addItems(["All", "Only fully completed", "Only not fully completed"])
        self.refresh_btn = QPushButton("Refresh")
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.completed_filter)
        filter_row.addWidget(self.refresh_btn)
        layout.addLayout(filter_row)

        splitter = QSplitter()
        self.list_widget = QListWidget()
        self.details_table = QTableWidget(0, 5)
        self.details_table.setHorizontalHeaderLabels(["Done", "Exercise", "Sets × Reps", "Load", "RIR"])
        self.details_table.horizontalHeader().setStretchLastSection(True)
        self.details_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.summary_label = QLabel("Select a workout to view details.")
        self.summary_label.setWordWrap(True)
        self.entry_notes = QPlainTextEdit()
        self.entry_notes.setReadOnly(True)
        self.entry_notes.setPlaceholderText("Warm-up notes")
        self.entry_notes.setFixedHeight(100)
        right_layout.addWidget(self.summary_label)
        right_layout.addWidget(self.details_table, 1)
        right_layout.addWidget(QLabel("Warm-up Notes"))
        right_layout.addWidget(self.entry_notes)

        splitter.addWidget(self.list_widget)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

        button_row = QHBoxLayout()
        self.edit_btn = QPushButton("Edit selected")
        self.delete_btn = QPushButton("Delete selected")
        self.export_btn = QPushButton("Export selected to Markdown")
        self.export_all_btn = QPushButton("Export all workout history")
        self.pdf_all_btn = QPushButton("PDF: All Dates")
        self.pdf_last7_btn = QPushButton("PDF: Last 7 Dates")
        self.pdf_range_btn = QPushButton("PDF: Custom Range")
        button_row.addWidget(self.edit_btn)
        button_row.addWidget(self.delete_btn)
        button_row.addWidget(self.pdf_all_btn)
        button_row.addWidget(self.pdf_last7_btn)
        button_row.addWidget(self.pdf_range_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.export_all_btn)
        button_row.addWidget(self.export_btn)
        layout.addLayout(button_row)

        self.list_widget.currentRowChanged.connect(self.show_history_details)
        self.search_edit.textChanged.connect(self.refresh_history)
        self.completed_filter.currentTextChanged.connect(self.refresh_history)
        self.refresh_btn.clicked.connect(self.refresh_history)
        self.delete_btn.clicked.connect(self.delete_selected_entry)
        self.edit_btn.clicked.connect(self.edit_selected_entry)
        self.export_btn.clicked.connect(self.export_selected_entry)
        self.export_all_btn.clicked.connect(self.export_all_history)
        self.pdf_all_btn.clicked.connect(self.export_workout_pdf_all_clicked)
        self.pdf_last7_btn.clicked.connect(self.export_workout_pdf_last7_clicked)
        self.pdf_range_btn.clicked.connect(self.export_workout_pdf_custom_range_clicked)

        self.refresh_history()

    def refresh_history(self) -> None:
        self.list_widget.clear()
        self.visible_entries = []

        query = self.search_edit.text().strip().lower()
        completion_mode = self.completed_filter.currentText()

        for entry in self.store.sorted_workout_history():
            exercises = entry.get("exercises", [])
            total = len(exercises)
            done = sum(1 for ex in exercises if ex.get("done"))
            fully_completed = total > 0 and done == total

            if completion_mode == "Only fully completed" and not fully_completed:
                continue
            if completion_mode == "Only not fully completed" and fully_completed:
                continue

            haystack = " ".join(
                [
                    entry.get("date", ""),
                    entry.get("template", ""),
                    entry.get("warmup_notes", entry.get("workout_notes", "")),
                    " ".join(ex.get("name", "") for ex in exercises),
                    " ".join(ex.get("notes", "") for ex in exercises),
                ]
            ).lower()

            if query and query not in haystack:
                continue

            self.visible_entries.append(entry)
            self.list_widget.addItem(QListWidgetItem(f"{entry.get('date', '')} | {entry.get('template', '')} | {done}/{total}"))

        if self.visible_entries:
            self.list_widget.setCurrentRow(0)
        else:
            self.show_history_details(-1)

    def show_history_details(self, row: int) -> None:
        self.details_table.setRowCount(0)
        if row < 0 or row >= len(self.visible_entries):
            self.summary_label.setText("Select a workout to view details.")
            self.entry_notes.clear()
            return

        entry = self.visible_entries[row]
        exercises = entry.get("exercises", [])
        total = len(exercises)
        done = sum(1 for ex in exercises if ex.get("done"))
        self.summary_label.setText(f"{entry.get('date', '')} — {entry.get('template', '')} — completed {done}/{total} exercises")
        self.entry_notes.setPlainText(entry.get("warmup_notes", entry.get("workout_notes", "")))

        self.details_table.setRowCount(len(exercises))
        for i, ex in enumerate(exercises):
            done_item = QTableWidgetItem("✓" if ex.get("done") else "")
            done_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.details_table.setItem(i, 0, done_item)
            self.details_table.setItem(i, 1, QTableWidgetItem(ex.get("name", "")))
            self.details_table.setItem(i, 2, QTableWidgetItem(ex.get("sets_reps", "")))
            self.details_table.setItem(i, 3, QTableWidgetItem(ex.get("target_load", "")))
            self.details_table.setItem(i, 4, QTableWidgetItem(ex.get("rir", "")))
        self.details_table.resizeColumnsToContents()

    def delete_selected_entry(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.visible_entries):
            return
        entry = self.visible_entries[row]
        confirm = QMessageBox.question(self, APP_TITLE, f"Delete workout entry for {entry.get('date')} ({entry.get('template')})?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_workout_entry(entry)
            self.refresh_history()
        except ValueError as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))

    def edit_selected_entry(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.visible_entries):
            return
        entry = self.visible_entries[row]
        dialog = EntryEditorDialog(self, self.store, entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated_entry = dialog.get_updated_entry()
        updated_entry["created_at"] = entry.get("created_at", updated_entry.get("created_at"))
        try:
            self.store.update_workout_entry(entry, updated_entry)
            self.refresh_history()
        except ValueError as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))

    def export_selected_entry(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.visible_entries):
            return
        entry = self.visible_entries[row]
        default_name = f"{entry.get('date', 'workout')}_{entry.get('template', 'entry').replace(' ', '_')}.md"
        path, _ = QFileDialog.getSaveFileName(self, "Export selected workout to Markdown", str(health_report_named_path(self.store, safe_filename_part(default_name.rsplit(".", 1)[0], "WorkoutEntry"), "md")), "Markdown Files (*.md)")
        if not path:
            return
        Path(path).write_text(self.entry_to_markdown(entry), encoding="utf-8")

    def export_all_history(self) -> None:
        default_path = health_report_named_path(self.store, "AllWorkoutHistory", "md")
        path, _ = QFileDialog.getSaveFileName(self, "Export all workout history to Markdown", str(default_path), "Markdown Files (*.md)")
        if not path:
            return

        parts = ["# Workout History\n\n"]

        # V2.2 export order:
        # Entry 1 should be the oldest workout entry.
        # The final Entry N should be the newest/latest entry.
        chronological_entries = sorted(
            self.store.workout_history(),
            key=lambda e: (e.get("date", ""), e.get("created_at", ""), e.get("template", "")),
        )

        for idx, entry in enumerate(chronological_entries, start=1):
            parts.append(f"## Entry {idx}\n\n")
            parts.append(self.entry_to_markdown(entry))
            parts.append("\n---\n\n")
        Path(path).write_text("".join(parts).rstrip() + "\n", encoding="utf-8")


    # -----------------------------
    # Workout PDF export (V3.0)
    # -----------------------------
    def workout_dates(self) -> List[str]:
        return sorted_iso_dates([stringify_value(entry.get("date", "")) for entry in self.store.workout_history()])

    def workout_entries_for_dates(self, dates: List[str]) -> List[dict]:
        allowed = set(dates)
        return sorted(
            [entry for entry in self.store.workout_history() if stringify_value(entry.get("date", "")) in allowed],
            key=lambda e: (e.get("date", ""), e.get("created_at", ""), e.get("template", "")),
        )

    def export_workout_pdf_all_clicked(self) -> None:
        dates = self.workout_dates()
        if not dates:
            QMessageBox.information(self, APP_TITLE, "No workout history found.")
            return
        self.export_workout_pdf_for_dates(dates, "All Dates", "AllWorkoutHistory")

    def export_workout_pdf_last7_clicked(self) -> None:
        dates = last_n_iso_dates(self.workout_dates(), 7)
        if not dates:
            QMessageBox.information(self, APP_TITLE, "No workout history found.")
            return
        self.export_workout_pdf_for_dates(dates, f"Last 7 Dates: {dates[0]} to {dates[-1]}", "Last7WorkoutHistory")

    def export_workout_pdf_custom_range_clicked(self) -> None:
        dates = ask_iso_date_range(self, "Export Workout PDF - Custom Range", self.workout_dates())
        if not dates:
            return
        self.export_workout_pdf_for_dates(dates, f"Custom Range: {dates[0]} to {dates[-1]}", "CustomWorkoutHistory")

    def export_workout_pdf_for_dates(self, dates: List[str], mode_label: str, suffix: str) -> None:
        entries = self.workout_entries_for_dates(dates)
        if not entries:
            QMessageBox.information(self, APP_TITLE, "No workout entries found for this PDF export.")
            return

        default_path = health_report_named_path(self.store, suffix, "pdf")
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Workout PDF - {mode_label}",
            str(default_path),
            "PDF Files (*.pdf)",
        )
        if not path:
            return

        try:
            body_html = self.build_workout_pdf_body(entries)
            subtitle = (
                f"Export mode: {mode_label}<br>"
                f"Source: {self.store.workout_history_path}<br>"
                f"Dates: {', '.join(dates)}<br>"
                f"Workout entries: {len(entries)}"
            )
            export_html_pdf(Path(path), "Workout History Report", subtitle, body_html, landscape=False)
            QMessageBox.information(self, APP_TITLE, f"Exported PDF:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, APP_TITLE, f"Workout PDF export failed:\n\n{exc}")

    def build_workout_pdf_body(self, entries: List[dict]) -> str:
        parts: List[str] = []
        parts.append("<h2>Summary</h2>")
        parts.append("<p class='small'>PDF exercise notes are shortened to keep one workout entry on one portrait page. Markdown exports keep full notes.</p>")
        parts.append("<table class='compact'><tr><th>#</th><th>Date</th><th>Template</th><th>Done</th><th>Created</th></tr>")
        for idx, entry in enumerate(entries, start=1):
            exercises = entry.get("exercises", [])
            total = len(exercises)
            done = sum(1 for ex in exercises if ex.get("done"))
            parts.append(
                "<tr>"
                f"<td class='num'>{idx}</td>"
                f"<td>{html_escape_text(entry.get('date', ''))}</td>"
                f"<td>{html_escape_text(entry.get('template', ''))}</td>"
                f"<td class='center'>{done}/{total}</td>"
                f"<td>{html_escape_text(entry.get('created_at', ''))}</td>"
                "</tr>"
            )
        parts.append("</table>")

        for idx, entry in enumerate(entries, start=1):
            parts.append("<div class='page-break'></div>")
            exercises = entry.get("exercises", [])
            total = len(exercises)
            done = sum(1 for ex in exercises if ex.get("done"))
            parts.append(f"<h2>Entry {idx}: {html_escape_text(entry.get('date', ''))} - {html_escape_text(entry.get('template', ''))}</h2>")
            parts.append(f"<p class='small'>Completed exercises: {done} / {total}</p>")

            warmup_notes = stringify_value(entry.get("warmup_notes", entry.get("workout_notes", ""))).strip()
            if warmup_notes:
                parts.append(f"<h3>Warm-up Notes <span class='truncated'>(shortened in PDF)</span></h3><div class='note'>{compact_pdf_text(warmup_notes, 170)}</div>")

            parts.append("<h3>Exercises</h3>")
            parts.append(
                "<table class='workout-table'>"
                "<tr><th style='width:5%'>✓</th><th style='width:23%'>Exercise</th><th style='width:12%'>Sets</th>"
                "<th style='width:15%'>Load</th><th style='width:6%'>RIR</th><th style='width:39%'>Notes</th></tr>"
            )
            for ex in exercises:
                done_text = "✓" if ex.get("done") else "—"
                parts.append(
                    "<tr>"
                    f"<td class='center'>{done_text}</td>"
                    f"<td>{html_escape_text(ex.get('name', ''))}</td>"
                    f"<td>{html_escape_text(ex.get('sets_reps', ''))}</td>"
                    f"<td>{html_escape_text(ex.get('target_load', ''))}</td>"
                    f"<td class='center'>{html_escape_text(ex.get('rir', ''))}</td>"
                    f"<td>{compact_pdf_text(ex.get('notes', ''), 95)}</td>"
                    "</tr>"
                )
            parts.append("</table>")
        return "".join(parts)


    def entry_to_markdown(self, entry: dict) -> str:
        lines = []
        lines.append(f"Date of workout: {entry.get('date', '')}\n")
        lines.append(f"Workout template: {entry.get('template', '')}\n\n")
        warmup_notes = entry.get("warmup_notes", entry.get("workout_notes", "")).strip()
        if warmup_notes:
            lines.append("Warm-up notes:\n")
            lines.append(f"{warmup_notes}\n\n")
        lines.append("| Exercise | Sets × Reps | Target Load | RIR After Sets | Done | Notes |\n")
        lines.append("| --- | ---: | --- | :---: | :---: | --- |\n")
        for ex in entry.get("exercises", []):
            done = "✓" if ex.get("done") else ""
            lines.append(
                f"| {ex.get('name', '')} | {ex.get('sets_reps', '')} | {ex.get('target_load', '')} | {ex.get('rir', '')} | {done} | {ex.get('notes', '')} |\n"
            )
        return "".join(lines)


class OverviewPage(QWidget):
    """
    V1.3 weekly overview.

    Instead of showing one selected day, this page shows the whole current week
    as seven columns. The real current day is highlighted.
    """

    def __init__(self, store: UnifiedStore):
        super().__init__()
        self.store = store
        self.current_week_start = self.week_start(date.today())

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.prev_week_btn = QPushButton("← Previous week")
        self.today_week_btn = QPushButton("This week")
        self.next_week_btn = QPushButton("Next week →")
        self.refresh_btn = QPushButton("Refresh")
        self.week_label = QLabel("")
        self.week_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        top.addWidget(self.prev_week_btn)
        top.addWidget(self.today_week_btn)
        top.addWidget(self.next_week_btn)
        top.addSpacing(20)
        top.addWidget(self.week_label, 1)
        top.addWidget(self.refresh_btn)
        root.addLayout(top)

        self.week_table = QTableWidget(1, 7)
        self.week_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.week_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.week_table.setWordWrap(True)
        self.week_table.verticalHeader().hide()
        self.week_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.week_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.week_table.setMinimumHeight(520)
        root.addWidget(self.week_table, 1)

        self.week_summary = QLabel("")
        self.week_summary.setWordWrap(True)
        self.week_summary.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.week_summary)

        self.prev_week_btn.clicked.connect(lambda: self.shift_week(-1))
        self.next_week_btn.clicked.connect(lambda: self.shift_week(1))
        self.today_week_btn.clicked.connect(self.go_current_week)
        self.refresh_btn.clicked.connect(self.refresh)

        self.refresh()

    def week_start(self, day: date) -> date:
        return day - timedelta(days=day.weekday())

    def shift_week(self, amount: int) -> None:
        self.current_week_start = self.current_week_start + timedelta(days=7 * amount)
        self.refresh()

    def go_current_week(self) -> None:
        self.current_week_start = self.week_start(date.today())
        self.refresh()

    def date_text(self, day: date) -> str:
        return day.isoformat()

    def summary_for_date(self, day: date) -> Dict[str, Any]:
        d = self.date_text(day)

        items = diet_log_items(self.store, d)
        target = diet_target_for_log(self.store, d)
        expenditure = diet_expenditure_for_log(self.store, d)

        diet_logs = self.store.data.get("diet", {}).get("logs", {})
        diet_log = diet_logs.get(d)
        checked = diet_log.get("checked", {}) if isinstance(diet_log, dict) else {}

        checklist_consumed = 0.0
        checked_count = 0
        for item in items:
            item_id = str(item.get("id", ""))
            if checked.get(item_id, False):
                checklist_consumed += parse_float(item.get("calories", 0), 0.0)
                checked_count += 1

        summary = compute_diet_energy(
            plan_total=sum(parse_float(item.get("calories", 0), 0.0) for item in items),
            checklist_consumed=checklist_consumed,
            additional_calories=parse_float(diet_log.get("additional_calories", ""), 0.0) if isinstance(diet_log, dict) else 0.0,
            additional_deficit=parse_float(diet_log.get("additional_deficit", ""), 0.0) if isinstance(diet_log, dict) else 0.0,
            target=target,
            expenditure=expenditure,
        )

        workouts = [entry for entry in self.store.workout_history() if entry.get("date") == d]
        workout_done = 0
        workout_total = 0
        workout_lines: List[str] = []
        for entry in workouts:
            exercises = entry.get("exercises", [])
            total = len(exercises)
            done = sum(1 for ex in exercises if ex.get("done"))
            workout_done += done
            workout_total += total
            workout_lines.append(f"{entry.get('template', '')}: {done}/{total}")

        summary.update({
            "date": d,
            "day": day,
            "diet_log": diet_log,
            "checked_count": checked_count,
            "total_items": len(items),
            "weight": diet_log.get("weight_kg", "") if isinstance(diet_log, dict) else "",
            "diet_note": diet_log.get("note", "") if isinstance(diet_log, dict) else "",
            "workouts": workouts,
            "workout_done": workout_done,
            "workout_total": workout_total,
            "workout_lines": workout_lines,
            "has_data": bool(diet_log or workouts),
        })
        return summary


    def build_day_text(self, summary: Dict[str, Any]) -> str:
        day: date = summary["day"]
        today = date.today()
        header = day.strftime("%A\n%Y-%m-%d")
        if day == today:
            header += "\n★ TODAY"

        lines = [header, "\n"]

        if summary["diet_log"]:
            template_label = ""
            if isinstance(summary["diet_log"], dict):
                template_label = short_diet_template_label(summary["diet_log"].get("diet_template_name", ""))
            lines.append(f"Diet — {template_label}\n" if template_label else "Diet\n")
            lines.append(f"  {summary['checked_count']}/{summary['total_items']} items\n")
            lines.append(f"  {summary['consumed']:.0f} kcal eaten\n")
            if summary["additional_calories"]:
                lines.append(f"  +{summary['additional_calories']:.0f} kcal extra\n")
            lines.append(f"  {summary['remaining']:.0f} kcal remaining\n")
            if summary["over"]:
                lines.append(f"  {summary['over']:.0f} kcal over target\n")
            if summary["additional_deficit"]:
                lines.append(f"  +{summary['additional_deficit']:.0f} kcal deficit adj.\n")
            lines.append(f"  Deficit: {summary['deficit']:.0f} kcal\n")
            if summary["weight"]:
                lines.append(f"  Weight: {summary['weight']} kg\n")
            note = str(summary["diet_note"] or "").strip()
            if note:
                short_note = note if len(note) <= 120 else note[:117] + "..."
                lines.append(f"  Note: {short_note}\n")
        else:
            lines.append("Diet\n")
            lines.append("  No log\n")

        lines.append("\nWorkout\n")
        if summary["workouts"]:
            lines.append(f"  {len(summary['workouts'])} entry/entries\n")
            if summary["workout_total"]:
                lines.append(f"  {summary['workout_done']}/{summary['workout_total']} exercises\n")
            for workout_line in summary["workout_lines"][:4]:
                lines.append(f"  - {workout_line}\n")
            if len(summary["workout_lines"]) > 4:
                lines.append(f"  ... +{len(summary['workout_lines']) - 4} more\n")
        else:
            lines.append("  No workout\n")

        return "".join(lines)

    def refresh(self) -> None:
        days = [self.current_week_start + timedelta(days=i) for i in range(7)]
        headers = [d.strftime("%a\n%m-%d") for d in days]
        self.week_table.setHorizontalHeaderLabels(headers)

        week_end = days[-1]
        self.week_label.setText(
            f"Week: {self.current_week_start.isoformat()} → {week_end.isoformat()}"
        )

        today = date.today()
        weekly_consumed = 0.0
        weekly_diet_days = 0
        weekly_workouts = 0
        weekly_ex_done = 0
        weekly_ex_total = 0

        for col, day in enumerate(days):
            summary = self.summary_for_date(day)
            weekly_consumed += summary["consumed"]
            if summary["diet_log"]:
                weekly_diet_days += 1
            weekly_workouts += len(summary["workouts"])
            weekly_ex_done += summary["workout_done"]
            weekly_ex_total += summary["workout_total"]

            item = QTableWidgetItem(self.build_day_text(summary))
            item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            font = QFont()
            font.setPointSize(10)

            if day == today:
                item.setBackground(QColor("#264653"))
                item.setForeground(QColor("#FFFFFF"))
                font.setBold(True)
            elif summary["has_data"]:
                item.setBackground(QColor("#102010"))
                item.setForeground(QColor("#E8FFE8"))
            else:
                item.setBackground(QColor("#111111"))
                item.setForeground(QColor("#D0D0D0"))

            item.setFont(font)
            self.week_table.setItem(0, col, item)

        self.week_table.resizeRowsToContents()
        if self.week_table.rowHeight(0) < 480:
            self.week_table.setRowHeight(0, 480)

        avg = weekly_consumed / weekly_diet_days if weekly_diet_days else 0
        self.week_summary.setText(
            f"Week summary: {weekly_diet_days}/7 diet days logged | "
            f"{weekly_consumed:.0f} kcal total logged | "
            f"{avg:.0f} kcal/day average on logged diet days | "
            f"{weekly_workouts} workout entry/entries | "
            f"{weekly_ex_done}/{weekly_ex_total} workout exercises completed"
        )


# -----------------------------
# Phone web app (mobile access over Windscribe port-forward)
# -----------------------------
def _phone_env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


PHONE_SERVER_ENABLED = _phone_env_flag("PHONE_SERVER_ENABLED", True)
PHONE_SERVER_PORT = int(os.environ.get("PHONE_SERVER_PORT", "20003"))


def _phone_default_lan_ip() -> str:
    """Best-effort LAN IP for the phone status URL when the user hasn't set
    PHONE_PUBLIC_HOST. Falls back to 0.0.0.0 if no usable address is found.
    """
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))  # routing lookup; no packet sent
            return sock.getsockname()[0]
        finally:
            sock.close()
    except Exception:
        return "0.0.0.0"


PHONE_PUBLIC_HOST = os.environ.get("PHONE_PUBLIC_HOST", "") or _phone_default_lan_ip()
PHONE_PUBLIC_PORT = int(os.environ.get("PHONE_PUBLIC_PORT", str(PHONE_SERVER_PORT)))


def _phone_env_file() -> Dict[str, str]:
    """Read DATA/HealthTracker/.env (KEY=VALUE lines) — holds secrets like the
    Cloudflare tunnel token. This file is gitignored; never hardcode secrets."""
    values: Dict[str, str] = {}
    try:
        path = get_health_data_dir() / ".env"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip().strip('"').strip("'")
    except Exception:
        pass
    return values


_PHONE_ENV = _phone_env_file()


def _phone_conf(name: str, default: str = "") -> str:
    """Config lookup: real environment variable wins, then the .env file."""
    return os.environ.get(name) or _PHONE_ENV.get(name, default)


# Cloudflare tunnel + installable-PWA settings (per PHONE_WEB_APP_PLAYBOOK.md).
PHONE_PUBLIC_URL = _phone_conf("APP_PUBLIC_URL", "")
PHONE_TUNNEL_TOKEN = _phone_conf("CLOUDFLARE_TUNNEL_TOKEN", "")
PHONE_TUNNEL_ENABLED = _phone_env_flag("PHONE_TUNNEL_ENABLED", True)
PHONE_ICON_VER = _phone_conf("PHONE_ICON_VER", "2")  # bump when icons change


class _PhoneRequest:
    __slots__ = ("fn", "event", "result", "error")

    def __init__(self, fn) -> None:
        self.fn = fn
        self.event = threading.Event()
        self.result: Any = None
        self.error: Optional[BaseException] = None


class PhoneBridge(QObject):
    """Runs all phone HTTP work on the Qt main thread.

    The HTTP server runs on a daemon thread and must never touch the store or
    widgets directly. It calls .call(fn); the queued signal makes fn run on the
    main thread (safe for store/widget access) while the HTTP thread blocks for
    the result. Blocking the HTTP worker thread is fine; the UI never blocks.
    """

    _submit = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._submit.connect(self._run)

    def _run(self, req: "_PhoneRequest") -> None:
        try:
            req.result = req.fn()
        except BaseException as exc:  # surfaced to the phone as an HTTP error
            req.error = exc
        finally:
            req.event.set()

    def call(self, fn, timeout: float = 15.0):
        req = _PhoneRequest(fn)
        self._submit.emit(req)
        if not req.event.wait(timeout):
            raise TimeoutError("App busy (a desktop dialog may be open). Try again.")
        if req.error is not None:
            raise req.error
        return req.result


def _render_icon_png_bytes(size: int) -> bytes:
    """Render the app .ico to a square PNG using only PyQt (no Pillow).

    Falls back to a generated branded tile so the phone's home-screen icon is
    never a broken/blank image. iOS snapshots this icon when the user picks
    "Add to Home Screen", so it just has to load reliably at that moment.
    """
    pix = QPixmap()
    icon_path = find_data_or_resource_file(APP_ICON_FILE)
    if icon_path.exists():
        rendered = QIcon(str(icon_path)).pixmap(QSize(size, size))
        if not rendered.isNull():
            pix = rendered
    if pix.isNull():
        pix = QPixmap(size, size)
        pix.fill(QColor("#6c5ce7"))
        painter = QPainter(pix)
        painter.setPen(QColor("#ffffff"))
        font = QFont("Arial", max(8, int(size * 0.42)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "HT")
        painter.end()
    if pix.size() != QSize(size, size):
        pix = pix.scaled(
            size, size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buffer, "PNG")
    return bytes(buffer_bytes)


def _render_maskable_png_bytes(size: int = 512) -> bytes:
    """Maskable launcher icon: the app icon scaled to FILL the whole tile so
    it occupies the full app-slot like normal apps (Android masks/rounds the
    corners). Backdrop is the app's dark background — NOT a loud purple — so
    any transparent edges blend in instead of glowing purple.
    """
    pix = QPixmap(size, size)
    pix.fill(QColor("#13121a"))
    src = QPixmap()
    icon_path = find_data_or_resource_file(APP_ICON_FILE)
    if icon_path.exists():
        src = QIcon(str(icon_path)).pixmap(QSize(size, size))
    painter = QPainter(pix)
    if not src.isNull():
        scaled = src.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    else:
        painter.setPen(QColor("#ffffff"))
        font = QFont("Arial", max(8, int(size * 0.46)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "HT")
    painter.end()
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buffer, "PNG")
    return bytes(buffer_bytes)


# 4-line no-op passthrough service worker (HTTPS-only). Must NOT precache, so
# app updates show on a plain refresh — see PHONE_WEB_APP_PLAYBOOK §12.5.
_PHONE_SW_JS = (
    "self.addEventListener('install',e=>self.skipWaiting());\n"
    "self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));\n"
    "self.addEventListener('fetch',e=>e.respondWith(fetch(e.request)));\n"
)


def _phone_manifest() -> str:
    v = PHONE_ICON_VER
    return json.dumps({
        "name": APP_TITLE,
        "short_name": "Fitness",
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0f0f13",
        "theme_color": "#6c5ce7",
        "icons": [
            {"src": f"/static/icon-192.png?v={v}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"/static/icon-512.png?v={v}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": f"/static/icon-maskable.png?v={v}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    })


# --- Phone data/actions. Every function here runs on the Qt main thread (via
# PhoneBridge) so it can safely drive the existing widgets. Driving the real
# DietChecklistPage / WorkoutBuilder means the fragile per-day snapshot logic is
# never reimplemented — the phone uses the exact same code path as the desktop.

def _phone_set_diet_date(dp: "DietChecklistPage", date_text: str) -> None:
    """Drive the desktop's date picker to `date_text` (fires load_day so the
    snapshot-safe save_current_day can write for the right date).

    Only call this from WRITE paths (toggle / fields / template / template
    delete). Read paths must NOT call it — a phone refresh used to silently
    switch the desktop's date to today and reload its widgets from the saved
    log, wiping the user's in-progress notes when today's saved value was
    empty.
    """
    qd = QDate.fromString(stringify_value(date_text), "yyyy-MM-dd")
    if not qd.isValid():
        return
    if dp.selected_date_text() != date_text:
        dp.date_edit.setDate(qd)  # fires on_date_changed -> load_day (rebuild)
    elif dp.current_date != date_text:
        dp.load_day(date_text)


def _phone_diet_state(window: "MainWindow", date_text: str) -> Dict[str, Any]:
    """Read-only diet state for the phone — computed from the STORE only.

    Crucially does NOT touch the desktop DietChecklistPage widgets; the
    phone refreshing must never yank the desktop's date or wipe its notes.
    Mirrors DietChecklistPage.rebuild_items / calculate_summary logic in
    pure-data form (per-day frozen-snapshot rules unchanged).
    """
    store = window.store
    text = stringify_value(date_text)
    if not is_iso_date_text(text):
        text = date.today().isoformat()

    logs = store.data.get("diet", {}).get("logs", {})
    raw_log = logs.get(text)
    log = raw_log if isinstance(raw_log, dict) else None

    # Template for this date: saved one if present, else configured default.
    template_name = stringify_value(log.get("diet_template_name", "")) if log else ""
    if not template_name:
        template_name = store.default_diet_template_name()

    # Items: prefer the saved per-day snapshot; otherwise the selected
    # template's current items. Mirrors DietChecklistPage.rebuild_items.
    has_snapshot = bool(log and isinstance(log.get("items_snapshot"), list) and log.get("items_snapshot"))
    has_checked_legacy = bool(log and isinstance(log.get("checked"), dict) and log.get("checked"))
    if has_snapshot or has_checked_legacy:
        items = diet_log_items(store, text, force_current_config=False)
    else:
        template_config = store.diet_config_for_template(template_name)
        items = diet_items_snapshot(template_config.get("items", []))

    checked_map = log.get("checked", {}) if log else {}
    weight_kg = stringify_value(log.get("weight_kg", "")) if log else ""
    additional_calories = stringify_value(log.get("additional_calories", "")) if log else ""
    additional_deficit = stringify_value(log.get("additional_deficit", "")) if log else ""
    note = stringify_value(log.get("note", "")) if log else ""

    plan_total = 0.0
    checklist_consumed = 0.0
    checked_count = 0
    phone_items: List[Dict[str, Any]] = []
    for it in items:
        cals = parse_float(it.get("calories", 0), 0.0)
        plan_total += cals
        item_id = str(it.get("id", ""))
        is_checked = bool(checked_map.get(item_id, False)) if isinstance(checked_map, dict) else False
        if is_checked:
            checklist_consumed += cals
            checked_count += 1
        phone_items.append({
            "id": item_id,
            "label": diet_item_checklist_label(it),
            "category": stringify_value(it.get("category", "Other")) or "Other",
            "calories": round(cals, 2),
            "checked": is_checked,
        })

    # Target / expenditure: frozen snapshot when the day has one, else fall
    # back to the selected template's current values (matches the desktop's
    # DietChecklistPage.calculate_summary "no log yet" branch).
    if log:
        target = diet_target_for_log(store, text)
        expenditure = diet_expenditure_for_log(store, text)
    else:
        template_config = store.diet_config_for_template(template_name)
        target = parse_float(template_config.get("target_calories", 0), 0.0)
        expenditure = parse_float(template_config.get("estimated_expenditure", 0), 0.0)

    summary = compute_diet_energy(
        plan_total=plan_total,
        checklist_consumed=checklist_consumed,
        additional_calories=parse_float(additional_calories, 0.0),
        additional_deficit=parse_float(additional_deficit, 0.0),
        target=target,
        expenditure=expenditure,
    )

    return {
        "date": text,
        "templates": store.diet_template_names(),
        "template": template_name,
        "items": phone_items,
        "fields": {
            "weight_kg": weight_kg,
            "additional_calories": additional_calories,
            "additional_deficit": additional_deficit,
            "note": note,
        },
        "summary": {
            "plan_total": round(summary["plan_total"], 0),
            "eaten": round(summary["consumed"], 0),
            "deficit": round(summary["deficit_pos"], 0),
            "surplus": round(summary["surplus"], 0),
        },
        "step_coeff": STEP_CALORIE_COEFFICIENT,
        "history_dates": sorted(logs.keys(), reverse=True),
    }


def _phone_diet_toggle(window: "MainWindow", date_text: str, item_id: Any, checked: Any) -> Dict[str, Any]:
    dp = window.diet_page
    _phone_set_diet_date(dp, date_text)
    cb = dp.check_vars.get(str(item_id))
    if cb is not None:
        cb.setChecked(bool(checked))  # autosaves via on_check_changed
    return _phone_diet_state(window, dp.current_date)


def _phone_eval_calc(text: Any) -> str:
    """Mirror the desktop calculator fields on the phone: '100+50' -> '150'.

    Same intent as DietChecklistPage.evaluate_adjustment_field (which only fires
    on the desktop's Enter key, so the phone never triggered it). Empty or
    invalid input is kept as-is instead of warning.
    """
    raw = stringify_value(text)
    if not raw.strip():
        return raw
    value = calculate_number_expression(raw)
    return format_number(value, 2) if value is not None else raw


def _phone_diet_fields(window: "MainWindow", date_text: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    dp = window.diet_page
    _phone_set_diet_date(dp, date_text)
    if "weight_kg" in fields:
        dp.weight_edit.setText(stringify_value(fields.get("weight_kg")))
    if "additional_calories" in fields:
        dp.additional_calories_edit.setText(_phone_eval_calc(fields.get("additional_calories")))
    if "additional_deficit" in fields:
        dp.additional_deficit_edit.setText(_phone_eval_calc(fields.get("additional_deficit")))
    if "note" in fields:
        dp.notes_edit.setPlainText(stringify_value(fields.get("note")))
    return _phone_diet_state(window, dp.current_date)


def _phone_diet_template(window: "MainWindow", date_text: str, template_name: Any) -> Dict[str, Any]:
    dp = window.diet_page
    _phone_set_diet_date(dp, date_text)
    name = stringify_value(template_name)
    # Mirror on_diet_template_changed's effect WITHOUT its confirm dialog (a
    # modal on the main thread would freeze the app waiting for desktop input).
    dp.set_diet_template_combo(name)
    dp.rebuild_items(date_text=dp.current_date, force_current_config=True)
    dp.set_diet_template_combo(name)
    dp.rendered_force_current_config = True
    dp.save_current_day(dp.current_date)
    dp.update_summary()
    return _phone_diet_state(window, dp.current_date)


def _phone_diet_history(window: "MainWindow") -> Dict[str, Any]:
    """Pure-store list of saved diet days for the phone history view.

    Does NOT call DietHistoryPage.refresh() — that would clear the desktop's
    list selection and details pane just because the phone polled. We iterate
    the store directly; DietHistoryPage.summary_for_date is already
    pure-data, so reusing it is safe.
    """
    php = window.diet_history_page
    logs = window.store.data.get("diet", {}).get("logs", {})
    days = []
    for d in sorted((k for k in logs.keys() if is_iso_date_text(k)), reverse=True):
        sm = php.summary_for_date(d)
        days.append({
            "date": d,
            "checked": sm["checked"],
            "total": sm["total"],
            "deficit": round(sm["deficit"], 0),
        })
    return {"days": days}


def _phone_diet_delete(window: "MainWindow", date_text: str) -> Dict[str, Any]:
    window.store.delete_diet_log(stringify_value(date_text))
    window.diet_history_page.refresh()
    window.diet_page.load_day(window.diet_page.current_date)
    window.overview_page.refresh()
    return _phone_diet_history(window)


def _phone_workout_state(window: "MainWindow", template_name: Optional[str] = None) -> Dict[str, Any]:
    builder = window.workout_log_page.builder
    if template_name and template_name in builder.templates and builder.template_combo.currentText() != template_name:
        builder.template_combo.setCurrentText(template_name)  # fires _on_template_changed
    exercises = []
    for row in builder.rows:
        exercises.append({
            "name": row.exercise.name,
            "amount": row.sets_reps_edit.text(),
            "load": row.load_edit.text(),
            "rir": row.rir_edit.text(),
            "rir_enabled": row.rir_edit.isEnabled(),
            "done": row.done_cb.isChecked(),
        })
    return {
        "templates": list(builder.templates.keys()),
        "template": builder.template_combo.currentText(),
        "date": builder.date_edit.date().toString("yyyy-MM-dd"),
        "exercises": exercises,
    }


def _phone_workout_save(window: "MainWindow", date_text: str, template_name: Any, exercises: List[dict]) -> Dict[str, Any]:
    wlp = window.workout_log_page
    builder = wlp.builder
    if not builder.templates:
        return {"ok": False, "message": "No workout templates are loaded."}
    name = stringify_value(template_name)
    if name and name in builder.templates and builder.template_combo.currentText() != name:
        builder.template_combo.setCurrentText(name)
    qd = QDate.fromString(stringify_value(date_text), "yyyy-MM-dd")
    if qd.isValid():
        builder.date_edit.setDate(qd)
    posted = exercises or []
    for i, row in enumerate(builder.rows):
        if i >= len(posted):
            break
        p = posted[i]
        if "amount" in p:
            row.sets_reps_edit.setText(stringify_value(p.get("amount")))
        if "load" in p:
            row.load_edit.setText(stringify_value(p.get("load")))
        if row.rir_edit.isEnabled() and "rir" in p:
            row.rir_edit.setText(stringify_value(p.get("rir")))
        if "done" in p:
            row.done_cb.setChecked(bool(p.get("done")))
    entry = builder.get_entry()
    # Save directly (skip wlp.save_workout — it pops a modal that would freeze
    # the main thread until the desktop user clicks OK).
    window.store.add_workout_entry(entry)
    window.workout_history_page.refresh_history()
    window.overview_page.refresh()
    return {"ok": True, "message": f"Workout saved for {entry['date']}.", "date": entry["date"]}


def _phone_workout_history(window: "MainWindow") -> Dict[str, Any]:
    entries = []
    for e in window.store.sorted_workout_history():
        exs = e.get("exercises", [])
        entries.append({
            "created_at": e.get("created_at", ""),
            "date": e.get("date", ""),
            "template": e.get("template", ""),
            "done": sum(1 for x in exs if x.get("done")),
            "total": len(exs),
            "exercises": [
                {
                    "name": x.get("name", ""),
                    "amount": x.get("sets_reps", ""),
                    "rir": x.get("rir", ""),
                    "done": bool(x.get("done")),
                }
                for x in exs
            ],
        })
    return {"entries": entries}


def _phone_workout_delete(window: "MainWindow", created_at: Any) -> Dict[str, Any]:
    key = stringify_value(created_at)
    target = None
    for e in window.store.workout_history():
        if stringify_value(e.get("created_at", "")) == key:
            target = e
            break
    if target is not None:
        try:
            window.store.delete_workout_entry(target)
        except ValueError:
            pass
        window.workout_history_page.refresh_history()
        window.overview_page.refresh()
    return _phone_workout_history(window)


def _phone_foods(window: "MainWindow") -> Dict[str, Any]:
    foods = []
    for f in window.store.get_foods():
        raw_units = f.get("units", {})
        units = raw_units if isinstance(raw_units, dict) else {"g": 1.0}
        foods.append({
            "id": str(f.get("id", "")),
            "name": str(f.get("name", "")),
            "kcal_per_g": parse_float(f.get("kcal_per_g", 0), 0.0),
            "default_unit": str(f.get("default_unit", "g")),
            "units": {str(k): parse_float(v, 1.0) for k, v in units.items()},
        })
    foods.sort(key=lambda x: x["name"].lower())
    return {"foods": foods}


def _phone_recipes(window: "MainWindow") -> Dict[str, Any]:
    recipes = []
    for r in sorted(window.store.get_recipes(), key=lambda x: str(x.get("name", "")).lower()):
        amount = parse_float(r.get("total_amount", 0), 0.0)
        cals = parse_float(r.get("total_calories", 0), 0.0)
        recipes.append({
            "name": str(r.get("name", "Recipe")),
            "total_amount": round(amount, 2),
            "unit": str(r.get("unit", "g")),
            "total_calories": round(cals, 2),
            "kcal_per_100g": round((cals / amount * 100.0) if amount else 0.0, 2),
            "notes": stringify_value(r.get("notes", "")),
            "ingredients": [
                {
                    "name": str(ing.get("name", "")),
                    "amount": round(parse_float(ing.get("amount", 0), 0.0), 2),
                    "unit": str(ing.get("unit", "g")),
                    "calories": round(parse_float(ing.get("calories", 0), 0.0), 2),
                }
                for ing in r.get("ingredients", []) if isinstance(ing, dict)
            ],
        })
    return {"recipes": recipes}


_PHONE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#6c5ce7">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Fitness">
<title>Home Fitness Tracker</title>
<link rel="manifest" href="/manifest.json?v=__ICONVER__">
<link rel="apple-touch-icon" href="/static/icon-180.png?v=__ICONVER__">
<link rel="apple-touch-icon" sizes="180x180" href="/static/icon-180.png?v=__ICONVER__">
<link rel="icon" type="image/png" href="/static/icon-192.png?v=__ICONVER__">
<script>if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').catch(function(){});});}</script>
<style>
:root{--bg:#0f0f13;--card:#191922;--card2:#222230;--fg:#d7d8e0;--mut:#8f93a8;--accent:#6c5ce7;--ok:#27c08a;--bad:#ff6b6b;--line:#312f3f}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;padding-bottom:74px}
h2{font-size:17px;margin:14px 4px 8px}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 10px 6px;border-bottom:1px solid var(--line)}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.grow{flex:1}
button,select,input,textarea{font:inherit;color:var(--fg);background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:10px}
button{background:var(--card2);cursor:pointer}
button.accent{background:var(--accent);border-color:var(--accent);font-weight:600}
button:active{opacity:.7}
.tabs{position:fixed;bottom:0;left:0;right:0;display:flex;background:var(--card);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}
.tabs button{flex:1;border:0;border-radius:0;background:var(--card);padding:12px 4px;color:var(--mut);font-size:13px}
.tabs button.on{color:var(--accent);font-weight:700}
.wrap{padding:8px 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;margin:8px 0}
.cat{color:var(--accent);font-weight:700;margin:14px 4px 4px;font-size:13px;text-transform:uppercase;letter-spacing:.04em}
.item{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin:6px 0}
.item.ck{border-color:var(--accent)}
.item .lab{flex:1;font-size:15px}
.item .kc{color:var(--mut);font-size:13px;white-space:nowrap}
.cbx{appearance:none;-webkit-appearance:none;margin:0;width:24px;height:24px;flex:none;border:2px solid #3a3850;border-radius:7px;background:var(--card2);position:relative;cursor:pointer;transition:background .12s,border-color .12s}
.cbx:checked{background:var(--accent);border-color:var(--accent)}
.cbx:checked::after{content:"";position:absolute;left:7px;top:3px;width:5px;height:10px;border:solid #fff;border-width:0 3px 3px 0;transform:rotate(45deg)}
.sum{display:grid;grid-template-columns:1fr 1fr;gap:6px 14px}
.sum div{display:flex;justify-content:space-between;border-bottom:1px dashed var(--line);padding:4px 0;font-size:14px}
.sum b{color:var(--accent)}
label{display:block;color:var(--mut);font-size:12px;margin:8px 2px 3px}
input,textarea,select{width:100%}
textarea{min-height:70px;resize:vertical}
.muted{color:var(--mut);font-size:13px;padding:8px 4px}
.del{background:transparent;border-color:var(--bad);color:var(--bad);padding:7px 10px;font-size:13px}
.hrow{display:flex;justify-content:space-between;align-items:center;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:6px 0}
.big{font-size:20px;font-weight:700}
.toast{position:fixed;left:50%;bottom:84px;transform:translateX(-50%);background:var(--accent);color:#fff;padding:10px 16px;border-radius:20px;opacity:0;transition:.2s;pointer-events:none;z-index:9}
.toast.show{opacity:1}
</style>
</head>
<body>
<div id="app"><div class="muted" style="padding:30px">Loading…</div></div>
<div class="tabs">
  <button data-t="diet" class="on">Diet</button>
  <button data-t="food">Food</button>
  <button data-t="recipe">Recipes</button>
  <button data-t="workout">Workout</button>
  <button data-t="history">History</button>
</div>
<div class="toast" id="toast"></div>
<script>
const E=document.getElementById('app'),TO=document.getElementById('toast');
let tab='diet',dietDate='',foods=null,hist='diet',stepS='',stepW='',stepCoeff=0.0004;
function toast(m){TO.textContent=m;TO.classList.add('show');clearTimeout(TO._t);TO._t=setTimeout(()=>TO.classList.remove('show'),1800);}
function esc(s){return (''+s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function api(path,opt){const r=await fetch(path,opt);const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j;}
function post(path,body){return api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{tab=b.dataset.t;document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));render();});

function fmtD(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
function todayStr(){return fmtD(new Date());}// phone's own local clock, not UTC/VPN
function shiftDate(n){const p=dietDate.split('-');const d=new Date(+p[0],+p[1]-1,+p[2]);d.setDate(d.getDate()+n);dietDate=fmtD(d);renderDiet();}
function sumHTML(q){return '<div><span>Plan Total</span><b>'+q.plan_total+'</b></div>'+
 '<div><span>Eaten</span><b>'+q.eaten+'</b></div>'+
 '<div><span>Deficit</span><b>'+q.deficit+'</b></div>'+
 '<div><span>Surplus</span><b>'+q.surplus+'</b></div>';}
function updateSummary(q){const el=document.getElementById('sum');if(el)el.innerHTML=sumHTML(q);}
function pSteps(v){v=(''+v).split(' ').join('');if(v.indexOf(',')>=0&&v.indexOf('.')<0)v=v.split(',').join('');return parseFloat(v)||0;}
function pNum(v){return parseFloat((''+v).replace(',','.'))||0;}
function stepCalc(){const el=document.getElementById('s_res');if(!el)return;const k=Math.max(pSteps(stepS)*pNum(stepW)*stepCoeff,0);el.textContent='= '+Math.round(k)+' kcal';}
async function renderDiet(){
 if(!dietDate)dietDate=todayStr();
 E.innerHTML='<div class="muted" style="padding:30px">Loading…</div>';
 let s;try{s=await api('/api/diet?date='+dietDate);}catch(e){E.innerHTML='<div class="card">'+esc(e.message)+'</div>';return;}
 dietDate=s.date;stepCoeff=s.step_coeff||stepCoeff;
 const cats=[...new Set(s.items.map(i=>i.category))];
 let h='<div class="bar"><div class="row"><button onclick="shiftDate(-1)">‹</button>'+
  '<input class="grow" type="date" value="'+s.date+'" onchange="dietDate=this.value;renderDiet()">'+
  '<button onclick="dietDate=todayStr();renderDiet()">Today</button>'+
  '<button onclick="shiftDate(1)">›</button></div>';
 if(s.templates.length){h+='<div class="row" style="margin-top:6px"><select class="grow" onchange="setTpl(this.value)">'+
  s.templates.map(t=>'<option'+(t===s.template?' selected':'')+'>'+esc(t)+'</option>').join('')+'</select></div>';}
 h+='</div><div class="wrap">';
 const q=s.summary;
 h+='<div class="card sum" id="sum">'+sumHTML(q)+'</div>';
 cats.forEach(c=>{h+='<div class="cat">'+esc(c)+'</div>';
  s.items.filter(i=>i.category===c).forEach(i=>{
   h+='<div class="item'+(i.checked?' ck':'')+'"><input class="cbx" type="checkbox" '+(i.checked?'checked':'')+
    ' onchange="tog(\\''+i.id+'\\',this.checked,this)"><div class="lab">'+esc(i.label)+'</div><div class="kc">'+i.calories+' kcal</div></div>';});});
 const f=s.fields;
 h+='<div class="card"><label>Weight kg</label><input id="f_w" value="'+esc(f.weight_kg)+'">'+
  '<label>Additional calories</label><input id="f_ac" value="'+esc(f.additional_calories)+'">'+
  '<label>Additional deficit / burn</label><input id="f_ad" value="'+esc(f.additional_deficit)+'">'+
  '<label>Notes</label><textarea id="f_n">'+esc(f.note)+'</textarea>'+
  '<div class="muted">Saved automatically when you leave a field.</div></div>';
 h+='<div class="card"><label>Step burn calculator — manual, not saved</label>'+
  '<div class="row"><input class="grow" id="s_st" inputmode="numeric" placeholder="steps" value="'+esc(stepS)+'">'+
  '<input class="grow" id="s_wt" inputmode="decimal" placeholder="kg" value="'+esc(stepW)+'"></div>'+
  '<div class="big" id="s_res">= 0 kcal</div>'+
  '<div class="muted">Read this, then type it into Deficit / Notes yourself.</div></div>';
 h+='</div>';
 E.innerHTML=h;
 ['f_w','f_ac','f_ad','f_n'].forEach(id=>{const el=document.getElementById(id);el.onblur=saveFields;});
 const _ss=document.getElementById('s_st'),_sw=document.getElementById('s_wt');
 _ss.oninput=()=>{stepS=_ss.value;stepCalc();};
 _sw.oninput=()=>{stepW=_sw.value;stepCalc();};
 stepCalc();
}
async function tog(id,ck,el){try{const s=await post('/api/diet/toggle',{date:dietDate,id:id,checked:ck});
 if(el)el.closest('.item').classList.toggle('ck',ck);updateSummary(s.summary);}catch(e){toast(e.message);if(el)el.checked=!ck;}}
async function saveFields(){try{
 const s=await post('/api/diet/fields',{date:dietDate,fields:{weight_kg:f_w.value,additional_calories:f_ac.value,additional_deficit:f_ad.value,note:f_n.value}});
 const set=(el,v)=>{if(el&&document.activeElement!==el)el.value=v;};
 set(f_w,s.fields.weight_kg);set(f_ac,s.fields.additional_calories);set(f_ad,s.fields.additional_deficit);set(f_n,s.fields.note);
 updateSummary(s.summary);toast('Saved');
 }catch(e){toast(e.message);}}
async function setTpl(t){try{await post('/api/diet/template',{date:dietDate,template:t});renderDiet();toast('Template set');}catch(e){toast(e.message);}}

async function renderFood(){
 if(!foods){try{foods=(await api('/api/foods')).foods;}catch(e){E.innerHTML='<div class="card">'+esc(e.message)+'</div>';return;}}
 let h='<div class="wrap"><h2>Food calculator</h2><div class="card">'+
  '<label>Search</label><input id="fq" placeholder="type to filter foods" oninput="foodFilter()">'+
  '<label>Food</label><select id="fd" onchange="foodUnits()"></select>'+
  '<label>Amount</label><input id="fa" value="100" inputmode="decimal" oninput="foodCalc()">'+
  '<label>Unit</label><select id="fu" onchange="foodCalc()"></select>'+
  '<div class="big" id="fr" style="margin-top:14px">—</div></div></div>';
 E.innerHTML=h;foodFilter();
}
function foodFilter(){const qel=document.getElementById('fq');const q=(qel?qel.value:'').toLowerCase().trim();
 const fd=document.getElementById('fd');
 const opts=foods.map((f,i)=>({i:i,f:f})).filter(o=>!q||o.f.name.toLowerCase().indexOf(q)>=0);
 fd.innerHTML=opts.length?opts.map(o=>'<option value="'+o.i+'">'+esc(o.f.name)+'</option>').join(''):'<option value="-1">No match</option>';
 foodUnits();}
function foodUnits(){const v=document.getElementById('fd').value;const u=document.getElementById('fu');
 if(v==='-1'||v===''){u.innerHTML='';document.getElementById('fr').textContent='—';return;}
 const f=foods[v];u.innerHTML=Object.keys(f.units).map(n=>'<option'+(n===f.default_unit?' selected':'')+'>'+esc(n)+'</option>').join('');foodCalc();}
function foodCalc(){const v=document.getElementById('fd').value;
 if(v==='-1'||v===''){document.getElementById('fr').textContent='—';return;}
 const f=foods[v];const a=parseFloat(document.getElementById('fa').value.replace(',','.'))||0;
 const g=a*(f.units[document.getElementById('fu').value]||1);const k=g*f.kcal_per_g;
 document.getElementById('fr').textContent=Math.round(k*10)/10+' kcal'+(document.getElementById('fu').value!=='g'?'  ('+Math.round(g*10)/10+' g)':'');}

let wk=null,wkTpl=null,wkDate='',wkEdits={};
function wkSet(i){const g=id=>document.getElementById(id),o={};
 if(g('wd'+i))o.done=g('wd'+i).checked;
 if(g('wa'+i))o.amount=g('wa'+i).value;
 if(g('wl'+i))o.load=g('wl'+i).value;
 if(g('wr'+i))o.rir=g('wr'+i).value;
 wkEdits[i]=o;}
async function renderWorkout(t){
 if(t!=null&&t!==wkTpl)wkEdits={};            // explicit template switch resets
 const want=(t!=null?t:wkTpl);                // tab-return keeps current template
 E.innerHTML='<div class="muted" style="padding:30px">Loading…</div>';
 try{wk=await api('/api/workout'+(want?'?template='+encodeURIComponent(want):''));}catch(e){E.innerHTML='<div class="card">'+esc(e.message)+'</div>';return;}
 wkTpl=wk.template;if(!wkDate)wkDate=wk.date;
 // 'today' refresh — if a previous session's cached date crossed midnight, bump
 // to the phone-local today and drop yesterday's in-progress edits.
 const _today=todayStr();if(wkDate<_today){wkDate=_today;wkEdits={};}
 let h='<div class="bar"><div class="row"><select class="grow" onchange="renderWorkout(this.value)">'+
  wk.templates.map(x=>'<option'+(x===wk.template?' selected':'')+'>'+esc(x)+'</option>').join('')+'</select>'+
  '<input type="date" id="wdate" value="'+wkDate+'" onchange="wkDate=this.value"></div></div><div class="wrap">';
 if(!wk.exercises.length)h+='<div class="muted">No exercises in this template.</div>';
 wk.exercises.forEach((x,i)=>{const e=wkEdits[i]||{};
  const dn=(e.done!=null?e.done:x.done),am=(e.amount!=null?e.amount:x.amount),ld=(e.load!=null?e.load:x.load),rr=(e.rir!=null?e.rir:x.rir);
  h+='<div class="card"><div class="row"><input type="checkbox" class="cbx" id="wd'+i+'" '+(dn?'checked':'')+' onchange="wkSet('+i+')"><div class="grow"><b>'+esc(x.name)+'</b></div></div>'+
   '<label>Amount (sets × reps)</label><input id="wa'+i+'" value="'+esc(am)+'" oninput="wkSet('+i+')">'+
   '<label>Load</label><input id="wl'+i+'" value="'+esc(ld)+'" oninput="wkSet('+i+')">'+
   (x.rir_enabled?'<label>RiR</label><input id="wr'+i+'" value="'+esc(rr)+'" inputmode="decimal" oninput="wkSet('+i+')">':'')+
   '</div>';});
 if(wk.exercises.length)h+='<button class="accent" style="width:100%;margin-top:10px" onclick="saveWk()">Save workout</button>';
 h+='</div>';E.innerHTML=h;
}
async function saveWk(){
 const ex=wk.exercises.map((x,i)=>{const e=wkEdits[i]||{};return{name:x.name,
  amount:((e.amount!=null?e.amount:x.amount)||''),
  load:((e.load!=null?e.load:x.load)||''),
  rir:x.rir_enabled?((e.rir!=null?e.rir:x.rir)||''):'',
  done:(e.done!=null?e.done:x.done)};});
 try{const r=await post('/api/workout/save',{date:wkDate||wk.date,template:wk.template,exercises:ex});
  toast(r.message||'Saved');}catch(e){toast(e.message);}
}

async function renderHistory(){
 let h='<div class="bar"><div class="row"><button class="grow'+(hist==='diet'?' accent':'')+'" onclick="hist=\\'diet\\';render()">Diet</button>'+
  '<button class="grow'+(hist==='workout'?' accent':'')+'" onclick="hist=\\'workout\\';render()">Workout</button></div></div><div class="wrap">';
 try{
  if(hist==='diet'){const d=await api('/api/diet/history');
   if(!d.days.length)h+='<div class="muted">No diet history.</div>';
   d.days.forEach(x=>{h+='<div class="hrow"><div><b>'+x.date+'</b><div class="muted">'+x.checked+'/'+x.total+' items · deficit '+x.deficit+'</div></div>'+
    '<button class="del" onclick="delDiet(\\''+x.date+'\\')">Delete</button></div>';});
  }else{const d=await api('/api/workout/history');
   if(!d.entries.length)h+='<div class="muted">No workout history.</div>';
   d.entries.forEach(x=>{h+='<div class="hrow"><div><b>'+esc(x.date)+'</b> · '+esc(x.template)+'<div class="muted">'+x.done+'/'+x.total+' done</div></div>'+
    '<button class="del" onclick="delWk(\\''+esc(x.created_at)+'\\')">Delete</button></div>';});}
 }catch(e){h+='<div class="card">'+esc(e.message)+'</div>';}
 h+='</div>';E.innerHTML=h;
}
async function delDiet(d){if(!confirm('Delete diet log '+d+'?'))return;try{await post('/api/diet/delete',{date:d});renderHistory();}catch(e){toast(e.message);}}
async function delWk(c){if(!confirm('Delete this workout entry?'))return;try{await post('/api/workout/delete',{created_at:c});renderHistory();}catch(e){toast(e.message);}}

async function renderRecipe(){
 E.innerHTML='<div class="muted" style="padding:30px">Loading…</div>';
 let d;try{d=await api('/api/recipes');}catch(e){E.innerHTML='<div class="card">'+esc(e.message)+'</div>';return;}
 window._recipes=d.recipes;
 E.innerHTML='<div class="bar"><input class="grow" id="rq" placeholder="search recipes or ingredients" oninput="recipeFilter()"></div><div class="wrap" id="rlist"></div>';
 recipeFilter();
}
function recipeFilter(){const qel=document.getElementById('rq');const q=(qel?qel.value:'').toLowerCase().trim();
 const list=(window._recipes||[]).filter(r=>!q||r.name.toLowerCase().indexOf(q)>=0||r.ingredients.some(i=>i.name.toLowerCase().indexOf(q)>=0));
 const box=document.getElementById('rlist');if(!box)return;
 if(!list.length){box.innerHTML='<div class="muted">No recipes.</div>';return;}
 box.innerHTML=list.map(r=>'<div class="card"><b>'+esc(r.name)+'</b>'+
  '<div class="muted">'+r.total_amount+' '+esc(r.unit)+' · '+r.total_calories+' kcal · '+r.kcal_per_100g+' kcal/100g</div>'+
  '<table style="width:100%;border-collapse:collapse;margin-top:6px;font-size:14px">'+
  r.ingredients.map(i=>'<tr><td>'+esc(i.name)+'</td><td style="text-align:right;color:var(--mut)">'+i.amount+' '+esc(i.unit)+'</td><td style="text-align:right">'+i.calories+'</td></tr>').join('')+
  '</table>'+(r.notes?'<div class="muted" style="margin-top:6px">'+esc(r.notes)+'</div>':'')+'</div>').join('');
}
function render(){if(tab==='diet')renderDiet();else if(tab==='food')renderFood();else if(tab==='recipe')renderRecipe();else if(tab==='workout')renderWorkout();else renderHistory();}
render();
</script>
</body>
</html>"""


def _phone_html() -> str:
    return _PHONE_HTML.replace("__ICONVER__", PHONE_ICON_VER)


def make_phone_handler(window: "MainWindow"):
    bridge: PhoneBridge = window._phone_bridge
    icons: Dict[Any, bytes] = window._phone_icons

    class PhoneHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # keep the desktop console quiet
            return

        def _send(self, code: int, body, ctype: str, cache: Any = False, extra: Optional[Dict[str, str]] = None) -> None:
            data = body.encode("utf-8") if isinstance(body, str) else body
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                if cache == "revalidate":
                    self.send_header("Cache-Control", "no-cache, must-revalidate")
                elif cache:
                    self.send_header("Cache-Control", "public, max-age=604800")
                else:
                    self.send_header("Cache-Control", "no-store")
                for key, value in (extra or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                pass

        def _json(self, code: int, obj: Any) -> None:
            self._send(code, json.dumps(obj), "application/json; charset=utf-8")

        def _read_body(self) -> Dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    return {}
                parsed = json.loads(self.rfile.read(length) or b"{}")
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

        def _run(self, fn) -> None:
            try:
                self._json(200, bridge.call(fn))
            except TimeoutError as exc:
                self._json(503, {"error": str(exc)})
            except Exception as exc:
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path in ("/", "/index.html"):
                return self._send(200, _phone_html(), "text/html; charset=utf-8")
            # PWA surface — must be reachable WITHOUT Cloudflare Access (the
            # bypass apps cover exactly these paths); never put secrets here.
            if path in ("/manifest.json", "/manifest.webmanifest"):
                return self._send(200, _phone_manifest(), "application/manifest+json; charset=utf-8", cache="revalidate")
            if path == "/sw.js":
                return self._send(200, _PHONE_SW_JS, "application/javascript; charset=utf-8",
                                   cache="revalidate", extra={"Service-Worker-Allowed": "/"})
            if path == "/static/icon-maskable.png":
                return self._send(200, icons["maskable"], "image/png", cache="revalidate")
            if path in ("/static/icon-180.png", "/static/icon-192.png", "/static/icon-512.png"):
                return self._send(200, icons[int(path.split("-")[1].split(".")[0])], "image/png", cache="revalidate")
            # Legacy plain-IP fallback paths (kept so old installs don't break).
            if path == "/favicon.ico":
                return self._send(200, icons["favicon"], "image/x-icon", cache=True)
            if path.startswith("/apple-touch-icon"):
                return self._send(200, icons[180], "image/png", cache=True)
            if path in ("/icon-180.png", "/icon-192.png", "/icon-512.png"):
                return self._send(200, icons[int(path.split("-")[1].split(".")[0])], "image/png", cache=True)
            if path == "/api/diet":
                d = (query.get("date") or [date.today().isoformat()])[0]
                return self._run(lambda: _phone_diet_state(window, d))
            if path == "/api/diet/history":
                return self._run(lambda: _phone_diet_history(window))
            if path == "/api/workout":
                t = (query.get("template") or [None])[0]
                return self._run(lambda: _phone_workout_state(window, t))
            if path == "/api/workout/history":
                return self._run(lambda: _phone_workout_history(window))
            if path == "/api/foods":
                return self._run(lambda: _phone_foods(window))
            if path == "/api/recipes":
                return self._run(lambda: _phone_recipes(window))
            return self._send(404, "Not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            body = self._read_body()
            if path == "/api/diet/toggle":
                return self._run(lambda: _phone_diet_toggle(window, body.get("date"), body.get("id"), body.get("checked")))
            if path == "/api/diet/fields":
                return self._run(lambda: _phone_diet_fields(window, body.get("date"), body.get("fields") or {}))
            if path == "/api/diet/template":
                return self._run(lambda: _phone_diet_template(window, body.get("date"), body.get("template")))
            if path == "/api/diet/delete":
                return self._run(lambda: _phone_diet_delete(window, body.get("date")))
            if path == "/api/workout/save":
                return self._run(lambda: _phone_workout_save(window, body.get("date"), body.get("template"), body.get("exercises") or []))
            if path == "/api/workout/delete":
                return self._run(lambda: _phone_workout_delete(window, body.get("created_at")))
            return self._send(404, "Not found", "text/plain; charset=utf-8")

    return PhoneHandler


def _find_cloudflared() -> Optional[str]:
    for candidate in (
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
    ):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("cloudflared")


def _kill_our_cloudflared(token: str) -> int:
    """Self-heal: kill any cloudflared.exe whose command line carries OUR
    token. Used at startup to clean up orphans from a previous run where the
    Job-object kill-on-close failed (e.g. on Windows). The token comparison
    happens in Python — the token never enters the shell command we invoke —
    so OTHER apps' cloudflared tunnels (different tokens) are not touched.
    """
    if not sys.platform.startswith("win") or not token:
        return 0
    try:
        flags = 0x08000000  # CREATE_NO_WINDOW
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe'\" | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=6, creationflags=flags,
        )
        raw = (result.stdout or "").strip()
        if not raw:
            return 0
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return 0
        killed = 0
        for item in data:
            cmd = item.get("CommandLine") or ""
            if token in cmd:
                pid = int(item.get("ProcessId") or 0)
                if pid > 0:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, creationflags=flags,
                    )
                    killed += 1
        return killed
    except Exception as exc:
        print(f"[tunnel] orphan-cleanup skipped: {exc}", flush=True)
        return 0


def _kill_on_close_job(proc: "subprocess.Popen") -> Any:
    """Put the child in a Windows Job with KILL_ON_JOB_CLOSE so a crashed or
    force-killed app can never leave an orphan cloudflared (which would serve
    502 to everyone). The returned handle must stay alive for the app's life.
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class BASIC(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IOC(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class EXTENDED(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC),
                ("IoInfo", IOC),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # CRITICAL — declare argtypes/restypes. Without these, HANDLEs default
        # to 32-bit ints and get truncated on 64-bit Python, so the calls
        # below would silently fail (return 0 with no exception) and the
        # child was never actually in the job → not killed when we exit.
        # That's the bug that left orphan cloudflared processes serving 502
        # to the phone. Don't remove these declarations.
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            print(f"[tunnel] CreateJobObject failed (err {ctypes.get_last_error()}); orphan-safety off.", flush=True)
            return None
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            print(f"[tunnel] SetInformationJobObject failed (err {ctypes.get_last_error()}); orphan-safety off.", flush=True)
            return None
        if not kernel32.AssignProcessToJobObject(job, int(proc._handle)):
            print(f"[tunnel] AssignProcessToJobObject failed (err {ctypes.get_last_error()}); orphan-safety off.", flush=True)
            return None
        return job
    except Exception as exc:
        print(f"[tunnel] Job-object setup error: {exc}", flush=True)
        return None


def _stop_cloudflared(window: "MainWindow") -> None:
    proc = getattr(window, "_cf_proc", None)
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass


def _start_cloudflared(window: "MainWindow") -> None:
    """Auto-run the named Cloudflare tunnel. Guarded — a tunnel failure must
    never block the local server (the plain-IP path still works)."""
    if not PHONE_TUNNEL_ENABLED:
        print("[tunnel] PHONE_TUNNEL_ENABLED=0; tunnel skipped.", flush=True)
        return
    token = (PHONE_TUNNEL_TOKEN or "").strip()
    if not token:
        print("[tunnel] no CLOUDFLARE_TUNNEL_TOKEN (DATA/HealthTracker/.env); tunnel skipped.", flush=True)
        return
    exe = _find_cloudflared()
    if not exe:
        print("[tunnel] cloudflared not found; install: winget Cloudflare.cloudflared", flush=True)
        return
    try:
        # Self-heal: kill any cloudflared from a prior run that still carries
        # OUR tunnel token (in case the Job-object kill-on-close ever fails).
        # Other apps' cloudflared (different tokens) are not touched.
        killed = _kill_our_cloudflared(token)
        if killed:
            print(f"[tunnel] cleaned up {killed} orphan cloudflared from a prior run.", flush=True)
        jobs_dir = get_health_data_dir() / "Jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        log_path = jobs_dir / "cloudflared.log"
        log_handle = open(log_path, "ab", buffering=0)
        creationflags = 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW
        proc = subprocess.Popen(
            [exe, "tunnel", "--no-autoupdate", "run", "--token", token],
            stdout=log_handle, stderr=log_handle, stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        window._cf_proc = proc
        window._cf_job = _kill_on_close_job(proc)  # keep handle alive on window
        window._cf_log = log_handle
        atexit.register(lambda: _stop_cloudflared(window))
        print(f"[tunnel] cloudflared running (pid {proc.pid}); log: {log_path}", flush=True)
    except Exception as exc:
        print(f"[tunnel] failed to start cloudflared: {exc}", flush=True)


def start_phone_server(window: "MainWindow") -> None:
    """Start the phone web server on a daemon thread. Never blocks the app."""
    if not PHONE_SERVER_ENABLED:
        return
    try:
        window._phone_bridge = PhoneBridge()
        window._phone_icons = {
            180: _render_icon_png_bytes(180),
            192: _render_icon_png_bytes(192),
            512: _render_icon_png_bytes(512),
            "maskable": _render_maskable_png_bytes(512),
        }
        ico_path = find_data_or_resource_file(APP_ICON_FILE)
        window._phone_icons["favicon"] = (
            ico_path.read_bytes() if ico_path.exists() else window._phone_icons[180]
        )
        server = ThreadingHTTPServer(("0.0.0.0", PHONE_SERVER_PORT), make_phone_handler(window))
        server.daemon_threads = True
        window._phone_server = server
        threading.Thread(target=server.serve_forever, name="HealthTrackerPhone", daemon=True).start()
        local = f"http://0.0.0.0:{PHONE_SERVER_PORT}/"
        public = PHONE_PUBLIC_URL or f"http://{PHONE_PUBLIC_HOST}:{PHONE_PUBLIC_PORT}/"
        print(f"[phone] serving {local}  ->  {public}", flush=True)
        window.statusBar().showMessage(f"Phone web app: {public}", 0)
        _start_cloudflared(window)
    except Exception as exc:
        print(f"[phone] disabled (startup failed): {exc}", flush=True)
        try:
            window.statusBar().showMessage(f"Phone web app failed to start: {exc}", 12000)
        except Exception:
            pass


# -----------------------------
# Main window
# -----------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app_dir = get_app_dir()
        self.store = UnifiedStore(self.app_dir)

        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.resize(1250, 865)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.overview_page = OverviewPage(self.store)
        self.diet_page = DietChecklistPage(self.store)
        self.diet_history_page = DietHistoryPage(self.store)
        self.recipes_page = RecipesPage(self.store)
        self.food_calculator_page = FoodCalculatorPage(self.store)
        self.workout_log_page = WorkoutLogPage(self.store)
        self.workout_history_page = WorkoutHistoryPage(self.store)

        self.tabs.addTab(self.overview_page, "Daily Overview")
        self.tabs.addTab(self.diet_page, "Diet Checklist")
        self.tabs.addTab(self.diet_history_page, "Diet History")
        self.tabs.addTab(self.recipes_page, "Recipes")
        self.tabs.addTab(self.food_calculator_page, "Food Calculator")
        self.tabs.addTab(self.workout_log_page, "Workout Log")
        self.tabs.addTab(self.workout_history_page, "Workout History")

        # Refresh "today" on the Workout Log tab when the app has been left
        # open across midnight — picker showed yesterday otherwise.
        self.tabs.currentChanged.connect(self._on_main_tab_changed)

        self.setup_menu()
        self.statusBar().showMessage(f"HealthTracker DATA folder: {self.store.data_dir}", 10000)

        if self.store.import_messages:
            self.statusBar().showMessage("Some data files were repaired or defaulted on load. Check the backups folder.", 8000)

        # Phone web app (mobile access). Daemon thread; wrapped so a server
        # failure can never stop the desktop app from running.
        start_phone_server(self)

    def _on_main_tab_changed(self, index: int) -> None:
        if index == self.tabs.indexOf(self.workout_log_page):
            self.workout_log_page.builder.refresh_today_if_stale()

    def setup_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        open_folder_action = QAction("Open data folder", self)
        open_folder_action.triggered.connect(lambda: open_folder(self.store.data_dir))

        show_paths_action = QAction("Show storage paths", self)
        show_paths_action.triggered.connect(self.show_storage_paths)

        export_json_action = QAction("Save backup copies of DATA JSON files", self)
        export_json_action.triggered.connect(self.backup_data_json_files)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)

        file_menu.addAction(open_folder_action)
        file_menu.addAction(show_paths_action)
        file_menu.addAction(export_json_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

    def show_storage_paths(self) -> None:
        msg = [
            f"Root DATA folder:\n{self.store.root_data_dir}",
            f"\nHealthTracker folder:\n{self.store.data_dir}",
            f"\nDietTracker folder:\n{self.store.diet_data_dir}",
            f"\nWorkoutTracker folder:\n{self.store.workout_data_dir}",
            f"\nDiet config:\n{self.store.diet_config_path}",
            f"\nDiet logs:\n{self.store.diet_logs_path}",
            f"\nWorkout templates:\n{self.store.workout_templates_path}",
            f"\nWorkout history:\n{self.store.workout_history_path}",
            f"\nRecipes:\n{self.store.recipes_path}",
            f"\nApp/exe folder:\n{self.app_dir}",
        ]
        QMessageBox.information(self, APP_TITLE, "\n".join(msg))

    def backup_data_json_files(self) -> None:
        default_dir = self.app_dir / f"HealthTracker_DATA_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        folder = QFileDialog.getExistingDirectory(self, "Choose backup folder", str(self.store.data_dir))
        if not folder:
            return

        backup_folder = Path(folder) / default_dir.name
        backup_folder.mkdir(parents=True, exist_ok=True)

        for path in [
            self.store.diet_config_path,
            self.store.diet_logs_path,
            self.store.workout_templates_path,
            self.store.workout_history_path,
            self.store.recipes_path,
            self.store.foods_path,
        ]:
            if path.exists():
                try:
                    relative = path.relative_to(self.store.data_dir)
                except ValueError:
                    relative = Path(path.name)
                target = backup_folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

        QMessageBox.information(self, APP_TITLE, f"Backup folder created:\n{backup_folder}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    apply_app_icon(app)
    window = MainWindow()
    apply_app_icon(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
