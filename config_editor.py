"""HealthTracker Config Editor - a companion desktop app for editing the
HealthTracker data files (foods, recipes, diet-config templates, workout
templates) without hand-editing JSON.

It is deliberately a SEPARATE app from ``health_tracker.py`` but reuses that
module's storage layer so the on-disk JSON shapes stay byte-compatible. It
imports ``health_tracker`` purely as a library: ``main()`` there is guarded by
``if __name__ == "__main__"`` and the phone server / cloudflared tunnel only
start inside ``MainWindow.__init__`` (which this app never constructs), so the
import has no side effects beyond defining helpers and the ``UnifiedStore``.

Each editor page is a ``QWidget`` whose ``__init__`` takes the shared
``UnifiedStore`` - the same contract every page in ``health_tracker.py`` uses -
so a refined page can later be lifted into the main app as a new tab with a
single ``addTab`` line.

Histories are intentionally OUT OF SCOPE: this app never reads or writes
``diet_logs.json`` or ``workout_history.json`` (their per-day frozen snapshots
are fragile). It edits the "configuration" files only.

Concurrency: the main HealthTracker app may be running while you edit here. Every
save first writes a timestamped backup into ``DATA/HealthTracker/backups/`` via
``UnifiedStore.backup_file``, each page has a "Reload from disk" button, and
saves remind you to hit "Reload config" / restart the main app so it picks up
the change.
"""

import copy
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import health_tracker as ht

APP_TITLE = "HealthTracker Config Editor"

# Shown on every page: editing here while the main app is open means two
# processes can write the same files, so the user must refresh the main app.
RELOAD_REMINDER = (
    "If HealthTracker is open, click 'Reload config' (Diet Checklist tab) "
    "or restart it so your changes show up."
)

# Dark theme, palette borrowed from the main app's WorkoutTimerDialog
# (#121212 / #eeeeee / #1f1f1f). The main app has no global stylesheet, so this
# lives only in the editor for now; the reused RecipesPage inherits it cleanly.
APP_QSS = """
    QMainWindow, QWidget, QDialog {
        background-color: #121212;
        color: #eeeeee;
        font-family: Segoe UI, sans-serif;
        font-size: 13px;
    }
    QTabWidget::pane { border: 1px solid #333333; border-top: none; }
    QTabBar::tab {
        background: #1a1a1a; color: #aaaaaa;
        border: 1px solid #333333; border-bottom: none;
        padding: 8px 18px; margin-right: 2px;
        border-top-left-radius: 8px; border-top-right-radius: 8px;
        font-weight: 600;
    }
    QTabBar::tab:selected { background: #1f1f1f; color: #ffffff; }
    QTabBar::tab:hover:!selected { background: #242424; color: #dddddd; }
    QPushButton {
        background-color: #1f1f1f; color: #ffffff;
        border: 1px solid #555555; border-radius: 8px;
        padding: 7px 12px; font-weight: 600;
    }
    QPushButton:hover { background-color: #333333; }
    QPushButton:disabled { background-color: #181818; color: #666666; border-color: #333333; }
    QLineEdit, QPlainTextEdit, QComboBox {
        background-color: #1a1a1a; color: #eeeeee;
        border: 1px solid #444444; border-radius: 6px; padding: 6px;
        selection-background-color: #3a5a9a;
    }
    QListWidget, QTableWidget {
        background-color: #1a1a1a; color: #eeeeee;
        border: 1px solid #444444; border-radius: 6px;
        selection-background-color: #2d4a7a;
    }
    QHeaderView::section {
        background-color: #1f1f1f; color: #cccccc;
        border: 1px solid #333333; padding: 4px;
    }
    QGroupBox {
        border: 1px solid #333333; border-radius: 8px;
        margin-top: 10px; padding-top: 8px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #bbbbbb; }
    QStatusBar { background: #0e0e0e; color: #999999; }
    QLabel#hint { color: #888888; font-size: 11px; }
"""


def backup_then_write(store: "ht.UnifiedStore", path: Path, data: Any) -> Optional[Path]:
    """Back up ``path`` (if it exists) then write ``data`` as pretty JSON.

    Returns the backup path (or None when there was nothing to back up). Uses the
    store's own helpers so the backup naming and the JSON format match the main
    app exactly.
    """
    backup = store.backup_file(path)
    ht.write_json(path, data)
    return backup


def _muted_label(text: str) -> QLabel:
    # Inline style (not the #hint QSS) so the hint text reads correctly whether
    # shown in the standalone app's dark theme OR embedded in the main app,
    # which has no global stylesheet. Matches the main app's help-text style.
    label = QLabel(text)
    label.setObjectName("hint")
    label.setStyleSheet("color: #888888; font-size: 11px;")
    label.setWordWrap(True)
    return label


def _num(value: Any, default: float = 0.0) -> Any:
    """Parse to a number, returning an int when the value is whole so the JSON
    stays clean (130, not 130.0) and hand-readable. Accepts the same expressions
    /unicode lookalikes ``parse_float`` does."""
    parsed = ht.parse_float(value, default)
    return int(parsed) if float(parsed).is_integer() else parsed


# ---------------------------------------------------------------------------
# Foods editor
# ---------------------------------------------------------------------------
class GlobalUnitsDialog(QDialog):
    """Edit the file-level ``global_units`` map (unit name -> grams per unit).

    These units are merged into every food's own unit list by the store on
    save, so they are the place to define units shared across all foods (e.g.
    ``g`` itself).
    """

    def __init__(self, parent: QWidget, global_units: Dict[str, float]):
        super().__init__(parent)
        self.setWindowTitle("Global units")
        self.resize(420, 420)
        layout = QVBoxLayout(self)

        layout.addWidget(_muted_label(
            "Units shared by every food. Value = grams for one of that unit "
            "(e.g. 'g' = 1). 'g' is always kept."
        ))

        self.table = _make_units_table()
        layout.addWidget(self.table)
        for unit_name, grams in global_units.items():
            _append_unit_row(self.table, unit_name, grams)

        row_buttons = QHBoxLayout()
        add_btn = QPushButton("Add unit")
        add_btn.clicked.connect(lambda: _append_unit_row(self.table, "", 1.0))
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(lambda: _remove_selected_row(self.table))
        row_buttons.addWidget(add_btn)
        row_buttons.addWidget(remove_btn)
        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_units(self) -> Dict[str, float]:
        units = _read_units_table(self.table)
        units.setdefault("g", 1.0)
        return units


def _make_units_table() -> QTableWidget:
    table = QTableWidget(0, 2)
    table.setHorizontalHeaderLabels(["Unit", "Grams per unit"])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    return table


def _append_unit_row(table: QTableWidget, unit_name: str, grams: Any) -> None:
    row = table.rowCount()
    table.insertRow(row)
    table.setItem(row, 0, QTableWidgetItem(str(unit_name)))
    table.setItem(row, 1, QTableWidgetItem(ht.format_number(grams)))


def _remove_selected_row(table: QTableWidget) -> None:
    rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
    for row in rows:
        table.removeRow(row)


def _read_units_table(table: QTableWidget) -> Dict[str, float]:
    """Read a units table into {name: grams}, dropping blank-name rows and any
    row whose grams don't parse to a positive number."""
    units: Dict[str, float] = {}
    for row in range(table.rowCount()):
        name_item = table.item(row, 0)
        grams_item = table.item(row, 1)
        name = (name_item.text().strip() if name_item else "")
        if not name:
            continue
        grams = ht.parse_float(grams_item.text() if grams_item else "", 0.0)
        if grams > 0:
            units[name] = grams
    return units


class FoodsEditorPage(QWidget):
    """Add / edit / delete entries in ``foods.json`` (the Food Calculator's
    database). Saves through ``UnifiedStore.save_foods_file`` so the wrapper
    (``schema_version`` / ``global_units`` / ``notes``) is preserved and ids are
    deduped exactly like the main app does."""

    def __init__(self, store: "ht.UnifiedStore"):
        super().__init__()
        self.store = store
        self._loading = False
        self.foods: List[dict] = []
        # Index of the currently-selected food within self.foods. We drive
        # selection off the row index, NOT off dicts stashed in QListWidgetItems:
        # QListWidgetItem.setData() does not preserve a Python dict by reference
        # (each .data() returns a fresh copy), which silently detaches edits.
        self._current_index = -1

        root = QVBoxLayout(self)
        root.addWidget(_muted_label(RELOAD_REMINDER))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # --- left: search + list + list actions ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search foods...")
        self.search_edit.textChanged.connect(self._apply_search)
        left_layout.addWidget(self.search_edit)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        left_layout.addWidget(self.list_widget, 1)

        list_buttons = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_food)
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_food)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_food)
        list_buttons.addWidget(add_btn)
        list_buttons.addWidget(self.duplicate_btn)
        list_buttons.addWidget(self.delete_btn)
        left_layout.addLayout(list_buttons)

        splitter.addWidget(left)

        # --- right: form for the selected food ---
        right = QWidget()
        form_layout = QVBoxLayout(right)

        details = QGroupBox("Food details")
        details_form = QFormLayout(details)

        id_row = QHBoxLayout()
        self.id_edit = QLineEdit()
        self.id_edit.setReadOnly(True)
        self.id_edit.setPlaceholderText("(assigned from name on save)")
        regen_btn = QPushButton("From name")
        regen_btn.setToolTip("Regenerate the id from the current name")
        regen_btn.clicked.connect(self._regenerate_id)
        id_row.addWidget(self.id_edit, 1)
        id_row.addWidget(regen_btn)
        details_form.addRow("id", id_row)

        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._refresh_current_item_text)
        details_form.addRow("name", self.name_edit)

        self.kcal_edit = QLineEdit()
        self.kcal_edit.setPlaceholderText("kcal per 1 gram, e.g. 0.88")
        details_form.addRow("kcal_per_g", self.kcal_edit)

        self.default_unit_combo = QComboBox()
        self.default_unit_combo.setEditable(True)
        details_form.addRow("default_unit", self.default_unit_combo)

        form_layout.addWidget(details)

        # --- units table ---
        units_group = QGroupBox("Units (name to grams per unit)")
        units_layout = QVBoxLayout(units_group)
        self.units_table = _make_units_table()
        self.units_table.cellChanged.connect(self._on_units_changed)
        units_layout.addWidget(self.units_table)
        unit_buttons = QHBoxLayout()
        add_unit_btn = QPushButton("Add unit")
        add_unit_btn.clicked.connect(lambda: _append_unit_row(self.units_table, "", 1.0))
        remove_unit_btn = QPushButton("Remove unit")
        remove_unit_btn.clicked.connect(lambda: _remove_selected_row(self.units_table))
        unit_buttons.addWidget(add_unit_btn)
        unit_buttons.addWidget(remove_unit_btn)
        unit_buttons.addStretch()
        units_layout.addLayout(unit_buttons)
        form_layout.addWidget(units_group)

        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QPlainTextEdit()
        notes_layout.addWidget(self.notes_edit)
        form_layout.addWidget(notes_group)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 720])

        # --- bottom action bar ---
        bottom = QHBoxLayout()
        global_btn = QPushButton("Global units...")
        global_btn.clicked.connect(self.edit_global_units)
        reload_btn = QPushButton("Reload from disk")
        reload_btn.clicked.connect(self.reload_from_disk)
        save_btn = QPushButton("Save foods")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save)
        self.status_label = _muted_label("")
        bottom.addWidget(global_btn)
        bottom.addWidget(reload_btn)
        bottom.addStretch()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(save_btn)
        root.addLayout(bottom)

        self._load_list()

    # -- data plumbing -------------------------------------------------------
    # store.get_foods() RE-NORMALIZES and rebuilds every food dict on each call,
    # so we fetch the live list ONCE per (re)load into self.foods and mutate that
    # same list in place. The list widget mirrors self.foods row-for-row; the
    # selected food is always self.foods[self.list_widget.currentRow()].
    def _load_list(self) -> None:
        self._loading = True
        self.foods = self.store.get_foods()
        self._current_index = -1
        self.list_widget.clear()
        for food in self.foods:
            self.list_widget.addItem(QListWidgetItem(self._display_name(food)))
        self._loading = False
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        else:
            self._clear_form()
        self._update_button_states()

    @staticmethod
    def _display_name(food: dict) -> str:
        name = str(food.get("name", "")).strip()
        return name or str(food.get("id", "") or "(unnamed)")

    def _apply_search(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            item.setHidden(needle not in item.text().lower())

    def _food_at(self, index: int) -> Optional[dict]:
        if 0 <= index < len(self.foods):
            return self.foods[index]
        return None

    def _current_food(self) -> Optional[dict]:
        return self._food_at(self.list_widget.currentRow())

    # -- selection / form binding -------------------------------------------
    def _on_row_changed(self, row: int) -> None:
        # Commit the form into the previously-selected food before loading the
        # new one. self._current_index tracks "previous"; -1 means skip (e.g.
        # right after a structural change that already committed/rebuilt).
        if not self._loading:
            previous = self._food_at(self._current_index)
            if previous is not None:
                self._commit_form_into(previous)
                prev_item = self.list_widget.item(self._current_index)
                if prev_item is not None:
                    prev_item.setText(self._display_name(previous))
        self._current_index = row
        food = self._food_at(row)
        if food is not None:
            self._load_food_into_form(food)
        else:
            self._clear_form()
        self._update_button_states()

    def _load_food_into_form(self, food: dict) -> None:
        self._loading = True
        self.id_edit.setText(str(food.get("id", "")))
        self.name_edit.setText(str(food.get("name", "")))
        self.kcal_edit.setText(ht.format_number(food.get("kcal_per_g", 0.0)))
        self.notes_edit.setPlainText(str(food.get("notes", "")))

        units = food.get("units", {}) or {"g": 1.0}
        self.units_table.setRowCount(0)
        for unit_name, grams in units.items():
            _append_unit_row(self.units_table, unit_name, grams)

        self.default_unit_combo.clear()
        self.default_unit_combo.addItems(list(units.keys()))
        self.default_unit_combo.setCurrentText(str(food.get("default_unit", "g")))
        self._loading = False

    def _clear_form(self) -> None:
        self._loading = True
        self.id_edit.clear()
        self.name_edit.clear()
        self.kcal_edit.clear()
        self.notes_edit.clear()
        self.units_table.setRowCount(0)
        self.default_unit_combo.clear()
        self._loading = False

    def _commit_form_into(self, food: Optional[dict]) -> None:
        if food is None:
            return
        food["name"] = self.name_edit.text().strip() or food.get("name", "")
        food["kcal_per_g"] = ht.parse_float(self.kcal_edit.text(), food.get("kcal_per_g", 0.0))
        food["notes"] = self.notes_edit.toPlainText().strip()

        units = _read_units_table(self.units_table)
        units.setdefault("g", 1.0)
        food["units"] = units

        default_unit = self.default_unit_combo.currentText().strip() or "g"
        if default_unit not in units:
            units[default_unit] = 1.0
        food["default_unit"] = default_unit

    def _commit_current(self) -> None:
        food = self._current_food()
        if food is not None:
            self._commit_form_into(food)
            item = self.list_widget.currentItem()
            if item is not None:
                item.setText(self._display_name(food))

    # -- small UI reactions --------------------------------------------------
    def _on_units_changed(self, *args) -> None:
        if self._loading:
            return
        # Keep default_unit choices in sync as the user edits unit names.
        current_default = self.default_unit_combo.currentText()
        names = []
        for row in range(self.units_table.rowCount()):
            cell = self.units_table.item(row, 0)
            if cell and cell.text().strip():
                names.append(cell.text().strip())
        self._loading = True
        self.default_unit_combo.clear()
        self.default_unit_combo.addItems(names)
        self.default_unit_combo.setCurrentText(current_default)
        self._loading = False

    def _refresh_current_item_text(self) -> None:
        food = self._current_food()
        item = self.list_widget.currentItem()
        if food is not None and item is not None:
            food["name"] = self.name_edit.text().strip() or food.get("name", "")
            item.setText(self._display_name(food))

    def _regenerate_id(self) -> None:
        name = self.name_edit.text().strip()
        new_id = self.store.safe_id(name, "")
        self.id_edit.setText(new_id)
        food = self._current_food()
        if food is not None:
            food["id"] = new_id

    def _update_button_states(self) -> None:
        has_selection = self._current_food() is not None
        self.duplicate_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    # -- list actions --------------------------------------------------------
    def _append_food(self, food: dict) -> None:
        """Append a food to both the model list and the widget (kept in lockstep
        order) and select it."""
        self.foods.append(food)
        self.list_widget.addItem(QListWidgetItem(self._display_name(food)))
        self.list_widget.setCurrentRow(len(self.foods) - 1)

    def add_food(self) -> None:
        self._commit_current()
        self._append_food({"id": "", "name": "New Food", "kcal_per_g": 0.0,
                           "default_unit": "g", "units": {"g": 1.0}, "notes": ""})
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def duplicate_food(self) -> None:
        self._commit_current()
        food = self._current_food()
        if food is None:
            return
        clone = copy.deepcopy(food)
        clone["id"] = ""  # re-derived from name on save
        clone["name"] = f"{clone.get('name', 'Food')} (copy)"
        self._append_food(clone)

    def delete_food(self) -> None:
        index = self.list_widget.currentRow()
        food = self._food_at(index)
        if food is None:
            return
        if QMessageBox.question(
            self, APP_TITLE,
            f"Delete '{self._display_name(food)}'?\n"
            "This only takes effect when you click Save foods.",
        ) != QMessageBox.StandardButton.Yes:
            return
        # Drop from model + widget together. Block signals during takeItem so the
        # mid-mutation currentRowChanged doesn't fire; -1 the tracked index so
        # the reselection below won't commit the form into the deleted slot.
        self._current_index = -1
        del self.foods[index]
        self.list_widget.blockSignals(True)
        self.list_widget.takeItem(index)
        self.list_widget.setCurrentRow(-1)
        self.list_widget.blockSignals(False)
        if self.list_widget.count():
            # Bounce through a real selection so _on_row_changed reloads the form
            # even when the target row number is unchanged.
            self.list_widget.setCurrentRow(min(index, self.list_widget.count() - 1))
        else:
            self._clear_form()
            self._update_button_states()

    # -- global units / reload / save ---------------------------------------
    def edit_global_units(self) -> None:
        self._commit_current()
        wrapper = self.store.data.get("foods", {})
        global_units = dict(wrapper.get("global_units", {"g": 1.0})) if isinstance(wrapper, dict) else {"g": 1.0}
        dialog = GlobalUnitsDialog(self, global_units)
        if dialog.exec() == QDialog.DialogCode.Accepted and isinstance(wrapper, dict):
            wrapper["global_units"] = dialog.result_units()
            self.status_label.setText("Global units updated - click Save foods to persist.")

    def reload_from_disk(self) -> None:
        if QMessageBox.question(
            self, APP_TITLE,
            "Reload foods.json from disk? Any unsaved edits here will be lost.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.store.reload_foods_file()
        self._load_list()
        self.status_label.setText("Reloaded from disk.")

    def save(self) -> None:
        self._commit_current()

        # Light validation: warn (don't block) on obviously-wrong rows.
        problems = []
        for food in self.foods:
            if not str(food.get("name", "")).strip():
                problems.append("a food has no name")
            if ht.parse_float(food.get("kcal_per_g", 0.0), -1.0) < 0:
                problems.append(f"'{self._display_name(food)}' has invalid kcal_per_g")
        if problems:
            unique = "\n".join(f"- {p}" for p in dict.fromkeys(problems))
            if QMessageBox.warning(
                self, APP_TITLE,
                f"Some entries look off:\n{unique}\n\nSave anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return

        backup = backup_then_write_foods(self.store)
        # Re-derived ids / normalization may have changed the list; reload it.
        self._load_list()
        where = f" (backup: {backup.name})" if backup else ""
        self.status_label.setText(f"Saved foods.json{where}. {RELOAD_REMINDER}")


def backup_then_write_foods(store: "ht.UnifiedStore") -> Optional[Path]:
    """Back up foods.json, then let the store re-normalize and write it.

    ``save_foods_file`` does the write itself, so we back up first and call it
    rather than routing through ``backup_then_write`` (which writes raw data and
    would bypass the wrapper normalization)."""
    backup = store.backup_file(store.foods_path)
    store.save_foods_file()
    return backup


# ---------------------------------------------------------------------------
# Diet config (template) editor
# ---------------------------------------------------------------------------
# Item table columns: (header, json key, kind). "num" cells parse to numbers.
_DIET_COLUMNS = [
    ("Name", "name", "str"),
    ("Amount", "amount", "num"),
    ("Unit", "unit", "str"),
    ("Calories", "calories", "num"),
    ("Category", "category", "str"),
]


class DietConfigEditorPage(QWidget):
    """Edit a diet-config *template* file (``diet_configs/*.json`` or a
    ``diet_config_*.json``) by hand-free table editing.

    The file is loaded as RAW JSON and written back raw, mutating the existing
    item dicts in place - so optional/unknown keys (``display_label``,
    ``hide_amount_in_checklist``, per-item ``notes``, anything hand-added) are
    preserved. Histories are never touched.
    """

    def __init__(self, store: "ht.UnifiedStore"):
        super().__init__()
        self.store = store
        self._loading = False
        self.files: List[Path] = []
        self.config: Dict[str, Any] = {}
        self.items: List[dict] = []

        root = QVBoxLayout(self)
        root.addWidget(_muted_label(RELOAD_REMINDER))

        # --- file selector row ---
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Template file:"))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._on_file_selected)
        file_row.addWidget(self.file_combo, 1)
        new_btn = QPushButton("New template...")
        new_btn.clicked.connect(self.new_template)
        reload_btn = QPushButton("Reload from disk")
        reload_btn.clicked.connect(self.reload_from_disk)
        file_row.addWidget(new_btn)
        file_row.addWidget(reload_btn)
        root.addLayout(file_row)

        # --- plan settings ---
        settings = QGroupBox("Plan settings")
        settings_form = QFormLayout(settings)
        self.version_edit = QLineEdit()
        self.version_edit.editingFinished.connect(
            lambda: self._set_config_num("config_version", self.version_edit, 1))
        self.target_edit = QLineEdit()
        self.target_edit.editingFinished.connect(self._on_target_changed)
        self.expenditure_edit = QLineEdit()
        self.expenditure_edit.editingFinished.connect(
            lambda: self._set_config_num("estimated_expenditure", self.expenditure_edit, 0))
        self.config_notes_edit = QPlainTextEdit()
        self.config_notes_edit.setFixedHeight(54)
        self.config_notes_edit.textChanged.connect(self._on_config_notes_changed)
        settings_form.addRow("config_version", self.version_edit)
        settings_form.addRow("target_calories", self.target_edit)
        settings_form.addRow("estimated_expenditure", self.expenditure_edit)
        settings_form.addRow("notes", self.config_notes_edit)
        root.addWidget(settings)

        # --- items table ---
        items_group = QGroupBox("Items")
        items_layout = QVBoxLayout(items_group)
        self.table = QTableWidget(0, len(_DIET_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _DIET_COLUMNS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(self._on_row_changed)
        items_layout.addWidget(self.table)

        item_buttons = QHBoxLayout()
        for label, slot in (
            ("Add", self.add_item), ("Duplicate", self.duplicate_item),
            ("Split in two", self.split_item), ("Delete", self.delete_item),
            ("↑", self.move_up), ("↓", self.move_down),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            item_buttons.addWidget(btn)
        item_buttons.addStretch()
        items_layout.addLayout(item_buttons)

        # --- per-item optional details ---
        detail = QGroupBox("Selected item - optional fields")
        detail_form = QFormLayout(detail)
        self.item_id_edit = QLineEdit()
        self.item_id_edit.editingFinished.connect(self._commit_item_id)
        self.item_display_edit = QLineEdit()
        self.item_display_edit.setPlaceholderText("display_label - shown instead of name if set")
        self.item_display_edit.editingFinished.connect(
            lambda: self._commit_item_opt("display_label", self.item_display_edit.text()))
        self.item_notes_edit = QLineEdit()
        self.item_notes_edit.setPlaceholderText("per-item notes (not shown on the checklist row)")
        self.item_notes_edit.editingFinished.connect(
            lambda: self._commit_item_opt("notes", self.item_notes_edit.text()))
        self.item_hide_check = QCheckBox("hide_amount_in_checklist")
        self.item_hide_check.toggled.connect(self._commit_item_hide)
        detail_form.addRow("id", self.item_id_edit)
        detail_form.addRow("display_label", self.item_display_edit)
        detail_form.addRow("notes", self.item_notes_edit)
        detail_form.addRow("", self.item_hide_check)
        items_layout.addWidget(detail)

        root.addWidget(items_group, 1)

        # --- bottom bar ---
        bottom = QHBoxLayout()
        self.total_label = QLabel("Plan total: -")
        self.total_label.setStyleSheet("font-weight: bold;")
        default_btn = QPushButton("Set as default template")
        default_btn.setToolTip("Use this template automatically for new blank days (writes diet_template_settings.json).")
        default_btn.clicked.connect(self.set_as_default)
        save_btn = QPushButton("Save template")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save)
        self.status_label = _muted_label("")
        bottom.addWidget(self.total_label)
        bottom.addStretch()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(default_btn)
        bottom.addWidget(save_btn)
        root.addLayout(bottom)

        self._refresh_file_list()

    # -- file list -----------------------------------------------------------
    def _discover_files(self) -> List[Path]:
        """External template files, plus the active diet_config.json if present
        (so it can be edited too - though it can't be 'set as default')."""
        files = list(self.store.external_diet_config_paths())
        if self.store.diet_config_path.exists():
            files.append(self.store.diet_config_path)
        return files

    def _file_label(self, path: Path) -> str:
        if path == self.store.diet_config_path:
            return f"{path.name}  (active fallback)"
        return path.name

    def _refresh_file_list(self, preferred: Optional[Path] = None) -> None:
        self._loading = True
        self.files = self._discover_files()
        self.file_combo.clear()
        for path in self.files:
            self.file_combo.addItem(self._file_label(path))
        self._loading = False
        if not self.files:
            self.config, self.items = {}, []
            self._load_into_widgets()
            self.status_label.setText("No template files found. Use 'New template...' to create one.")
            return
        index = 0
        if preferred is not None:
            for i, path in enumerate(self.files):
                if path == preferred:
                    index = i
                    break
        if self.file_combo.currentIndex() == index:
            self._on_file_selected(index)  # currentIndexChanged won't fire for same index
        else:
            self.file_combo.setCurrentIndex(index)

    def _current_path(self) -> Optional[Path]:
        index = self.file_combo.currentIndex()
        if 0 <= index < len(self.files):
            return self.files[index]
        return None

    def _on_file_selected(self, index: int) -> None:
        if self._loading or not (0 <= index < len(self.files)):
            return
        path = self.files[index]
        try:
            loaded = ht.read_json(path)
            if not isinstance(loaded, dict):
                raise ValueError("file is not a JSON object")
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, f"Could not read {path.name}:\n{exc}")
            self.config, self.items = {}, []
            self._load_into_widgets()
            return
        self.config = loaded
        items = self.config.get("items")
        if not isinstance(items, list):
            items = []
            self.config["items"] = items
        self.items = items
        self._load_into_widgets()
        self.status_label.setText(f"Loaded {path.name}.")

    # -- populate widgets ----------------------------------------------------
    def _load_into_widgets(self) -> None:
        self._loading = True
        self.version_edit.setText(ht.format_number(self.config.get("config_version", 1)))
        self.target_edit.setText(ht.format_number(self.config.get("target_calories", 0)))
        self.expenditure_edit.setText(ht.format_number(self.config.get("estimated_expenditure", 0)))
        self.config_notes_edit.setPlainText(str(self.config.get("notes", "")))
        self._populate_table()
        self._loading = False
        self._load_item_detail()
        self._recompute_total()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for item in self.items:
            self._append_table_row(item)

    def _append_table_row(self, item: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, (_, key, kind) in enumerate(_DIET_COLUMNS):
            value = item.get(key, "")
            text = ht.format_number(value) if kind == "num" else str(value)
            self.table.setItem(row, col, QTableWidgetItem(text))

    # -- table editing -------------------------------------------------------
    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._loading or not (0 <= row < len(self.items)):
            return
        _, key, kind = _DIET_COLUMNS[col]
        cell = self.table.item(row, col)
        if cell is None:
            return
        text = cell.text()
        if kind == "num":
            number = _num(text, self.items[row].get(key, 0))
            self.items[row][key] = number
            self._loading = True
            cell.setText(ht.format_number(number))  # canonicalize display
            self._loading = False
            if key == "calories":
                self._recompute_total()
        else:
            self.items[row][key] = text.strip()

    def _on_row_changed(self, row: int, col: int, prev_row: int, prev_col: int) -> None:
        if row != prev_row:
            self._load_item_detail()

    # -- selected-item detail ------------------------------------------------
    def _selected_item(self) -> Optional[dict]:
        row = self.table.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row]
        return None

    def _load_item_detail(self) -> None:
        item = self._selected_item()
        self._loading = True
        if item is None:
            self.item_id_edit.clear()
            self.item_display_edit.clear()
            self.item_notes_edit.clear()
            self.item_hide_check.setChecked(False)
            self._set_detail_enabled(False)
        else:
            self._set_detail_enabled(True)
            self.item_id_edit.setText(str(item.get("id", "")))
            self.item_display_edit.setText(str(item.get("display_label", "")))
            self.item_notes_edit.setText(str(item.get("notes", "")))
            self.item_hide_check.setChecked(bool(item.get("hide_amount_in_checklist", False)))
        self._loading = False

    def _set_detail_enabled(self, enabled: bool) -> None:
        for widget in (self.item_id_edit, self.item_display_edit,
                       self.item_notes_edit, self.item_hide_check):
            widget.setEnabled(enabled)

    def _commit_item_id(self) -> None:
        if self._loading:
            return
        item = self._selected_item()
        if item is not None:
            item["id"] = self.item_id_edit.text().strip()

    def _commit_item_opt(self, key: str, value: str) -> None:
        """Set an optional string field, or remove the key when blank so the
        file stays tidy (these fields are documented as optional)."""
        if self._loading:
            return
        item = self._selected_item()
        if item is None:
            return
        value = value.strip()
        if value:
            item[key] = value
        else:
            item.pop(key, None)

    def _commit_item_hide(self, checked: bool) -> None:
        if self._loading:
            return
        item = self._selected_item()
        if item is None:
            return
        if checked:
            item["hide_amount_in_checklist"] = True
        else:
            item.pop("hide_amount_in_checklist", None)

    # -- plan settings binding ----------------------------------------------
    def _set_config_num(self, key: str, edit: QLineEdit, default: float) -> None:
        if self._loading:
            return
        number = _num(edit.text(), default)
        self.config[key] = number
        self._loading = True
        edit.setText(ht.format_number(number))
        self._loading = False

    def _on_target_changed(self) -> None:
        self._set_config_num("target_calories", self.target_edit, 0)
        self._recompute_total()

    def _on_config_notes_changed(self) -> None:
        if self._loading:
            return
        self.config["notes"] = self.config_notes_edit.toPlainText()

    def _recompute_total(self) -> None:
        total = sum(ht.parse_float(item.get("calories", 0), 0.0) for item in self.items)
        target = ht.parse_float(self.config.get("target_calories", 0), 0.0)
        delta = total - target
        sign = "+" if delta >= 0 else "-"
        self.total_label.setText(
            f"Plan total: {ht.format_number(total)} kcal   |   target "
            f"{ht.format_number(target)}   |   Δ {sign}{ht.format_number(abs(delta))}"
        )

    # -- item actions --------------------------------------------------------
    def _select_row(self, row: int) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.setCurrentCell(row, 0)

    def add_item(self) -> None:
        item = {"id": "", "name": "New item", "amount": 0, "unit": "g",
                "calories": 0, "category": "Other"}
        self.items.append(item)
        self._loading = True
        self._append_table_row(item)
        self._loading = False
        self._select_row(len(self.items) - 1)
        self._recompute_total()

    def duplicate_item(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        clone = copy.deepcopy(item)
        index = self.table.currentRow() + 1
        self.items.insert(index, clone)
        self._reload_table_keep_selection(index)
        self._recompute_total()

    def split_item(self) -> None:
        """Split the selected item into two halves (the split-item convention):
        unique ``_1``/``_2`` ids, identical name/category, amount & calories
        halved so the totals are unchanged."""
        row = self.table.currentRow()
        item = self._selected_item()
        if item is None:
            return
        import re
        base_id = re.sub(r"_(\d+)(of\d+)?$", "", str(item.get("id", "")).strip()) or "item"
        a1, a2 = _split_number(item.get("amount", 0))
        c1, c2 = _split_number(item.get("calories", 0))
        first = copy.deepcopy(item)
        first["id"], first["amount"], first["calories"] = f"{base_id}_1", a1, c1
        second = copy.deepcopy(item)
        second["id"], second["amount"], second["calories"] = f"{base_id}_2", a2, c2
        self.items[row:row + 1] = [first, second]
        self._reload_table_keep_selection(row)
        self._recompute_total()

    def delete_item(self) -> None:
        row = self.table.currentRow()
        item = self._selected_item()
        if item is None:
            return
        name = item.get("name", "this item")
        if QMessageBox.question(
            self, APP_TITLE,
            f"Delete '{name}'?\nThis only takes effect when you click Save template.",
        ) != QMessageBox.StandardButton.Yes:
            return
        del self.items[row]
        self._reload_table_keep_selection(min(row, len(self.items) - 1))
        self._recompute_total()

    def move_up(self) -> None:
        self._move(-1)

    def move_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        row = self.table.currentRow()
        target = row + delta
        if not (0 <= row < len(self.items) and 0 <= target < len(self.items)):
            return
        self.items[row], self.items[target] = self.items[target], self.items[row]
        self._reload_table_keep_selection(target)

    def _reload_table_keep_selection(self, row: int) -> None:
        self._loading = True
        self._populate_table()
        self._loading = False
        self._select_row(row)
        self._load_item_detail()

    # -- new file / default / reload / save ---------------------------------
    def new_template(self) -> None:
        name, ok = QInputDialog.getText(
            self, "New diet template",
            "Template name (e.g. 2026-06-20 or Low Carb Day):")
        if not ok or not name.strip():
            return
        safe = ht.re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_") or "template"
        path = self.store.diet_templates_dir / f"diet_config_{safe}.json"
        if path.exists():
            QMessageBox.warning(self, APP_TITLE, f"{path.name} already exists.")
            return
        skeleton = {"config_version": 1, "target_calories": 0,
                    "estimated_expenditure": 0, "notes": "", "items": []}
        ht.write_json(path, skeleton)
        self._refresh_file_list(preferred=path)
        self.status_label.setText(f"Created {path.name}. Add items and Save.")

    def set_as_default(self) -> None:
        path = self._current_path()
        if path is None:
            return
        if path == self.store.diet_config_path:
            QMessageBox.information(
                self, APP_TITLE,
                "The active diet_config.json is the fallback, not a selectable "
                "template - pick a diet_configs/* file to set as default.")
            return
        # Resolve the file to the display name the store would show, so the
        # written default matches diet_template_map()'s key exactly.
        display_name = None
        for name, payload in self.store.diet_template_map().items():
            ext = payload.get("_external_template_file")
            if ext and Path(ext).resolve() == path.resolve():
                display_name = name
                break
        if display_name is None:
            QMessageBox.information(
                self, APP_TITLE,
                "Save the template first, then set it as default.")
            return
        self.store.set_default_diet_template_name(display_name)
        self.status_label.setText(
            f"'{display_name}' is now the default for new days. {RELOAD_REMINDER}")

    def reload_from_disk(self) -> None:
        path = self._current_path()
        if path is None:
            self._refresh_file_list()
            return
        if QMessageBox.question(
            self, APP_TITLE,
            f"Reload {path.name} from disk? Unsaved edits here will be lost.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self._refresh_file_list(preferred=path)
        self.status_label.setText("Reloaded from disk.")

    def save(self) -> None:
        path = self._current_path()
        if path is None:
            QMessageBox.information(self, APP_TITLE, "No template selected.")
            return

        # Validate: unique ids within the file (warn, non-blocking).
        ids = [str(item.get("id", "")).strip() for item in self.items]
        dupes = {i for i in ids if i and ids.count(i) > 1}
        if dupes:
            if QMessageBox.warning(
                self, APP_TITLE,
                "Duplicate item ids in this file:\n"
                + ", ".join(sorted(dupes))
                + "\n\nThe app will auto-suffix duplicates on load, which can "
                "orphan history. Save anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return

        backup = backup_then_write(self.store, path, self.config)
        where = f" (backup: {backup.name})" if backup else ""
        self.status_label.setText(f"Saved {path.name}{where}. {RELOAD_REMINDER}")


def _split_number(value: Any) -> tuple:
    """Halve a number into two parts whose sum equals the original, each cleaned
    to int-when-whole. e.g. 260 -> (130, 130); 228.8 -> (114.4, 114.4)."""
    total = ht.parse_float(value, 0.0)
    first = round(total / 2, 4)
    second = round(total - first, 4)
    return _num(first), _num(second)


# ---------------------------------------------------------------------------
# Workout template editor
# ---------------------------------------------------------------------------
# Exercise table columns (all free text). hiit-only fields live in the detail
# panel; any other/unknown keys are preserved by editing dicts in place.
_WORKOUT_COLUMNS = [
    ("Name", "name"),
    ("Sets × Reps", "sets_reps"),
    ("Target load", "target_load"),
    ("Notes", "notes"),
]


class WorkoutTemplateEditorPage(QWidget):
    """Edit ``workout_templates.json`` - the object of
    ``{ "Template Name": {template}, ... }``.

    Loaded and saved as RAW JSON (never round-tripped through the store's
    WorkoutTemplate objects), editing the existing dicts in place, so the
    schema-flexible / unknown fields (hiit keys, ``_last_completed``, hand-added
    keys) survive exactly. Workout *history* is never touched.
    """

    def __init__(self, store: "ht.UnifiedStore"):
        super().__init__()
        self.store = store
        self._loading = False
        self.templates: Dict[str, dict] = {}
        self.names: List[str] = []          # display order, mirrors the list
        self._current_index = -1
        self.exercises: List[dict] = []     # current template's exercise list

        root = QVBoxLayout(self)
        root.addWidget(_muted_label(
            "Edits workout_templates.json only - never your workout history. " + RELOAD_REMINDER))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # --- left: template list + actions ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Templates"))
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self._on_template_changed)
        left_layout.addWidget(self.template_list, 1)
        tmpl_buttons = QHBoxLayout()
        for label, slot in (("Add", self.add_template), ("Rename", self.rename_template),
                            ("Duplicate", self.duplicate_template), ("Delete", self.delete_template)):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            tmpl_buttons.addWidget(btn)
        left_layout.addLayout(tmpl_buttons)
        splitter.addWidget(left)

        # --- right: meta + exercises + detail ---
        right = QWidget()
        right_layout = QVBoxLayout(right)

        meta = QGroupBox("Template settings")
        meta_form = QFormLayout(meta)
        self.rest_edit = QLineEdit()
        self.rest_edit.editingFinished.connect(
            lambda: self._set_meta_num("_default_rest_seconds", self.rest_edit, 75))
        self.warmup_edit = QPlainTextEdit()
        self.warmup_edit.setFixedHeight(54)
        self.warmup_edit.textChanged.connect(self._on_warmup_changed)
        self.last_completed_edit = QLineEdit()
        self.last_completed_edit.editingFinished.connect(self._commit_last_completed)
        meta_form.addRow("_default_rest_seconds", self.rest_edit)
        meta_form.addRow("_warmup_notes", self.warmup_edit)
        meta_form.addRow("_last_completed", self.last_completed_edit)
        right_layout.addWidget(meta)

        ex_group = QGroupBox("Exercises")
        ex_layout = QVBoxLayout(ex_group)
        self.table = QTableWidget(0, len(_WORKOUT_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _WORKOUT_COLUMNS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(self._on_exercise_row_changed)
        ex_layout.addWidget(self.table)
        ex_buttons = QHBoxLayout()
        for label, slot in (("Add", self.add_exercise), ("Duplicate", self.duplicate_exercise),
                            ("Delete", self.delete_exercise), ("↑", self.move_up), ("↓", self.move_down)):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            ex_buttons.addWidget(btn)
        ex_buttons.addStretch()
        ex_layout.addLayout(ex_buttons)

        detail = QGroupBox("Selected exercise - options")
        detail_form = QFormLayout(detail)
        self.no_rir_check = QCheckBox("No RIR (warm-up / mobility - hides the RIR box in the Workout Log)")
        self.no_rir_check.toggled.connect(self._commit_no_rir)
        detail_form.addRow("", self.no_rir_check)
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("e.g. hiit_step - makes this a timed HIIT step")
        self.type_edit.editingFinished.connect(
            lambda: self._commit_ex_opt("type", self.type_edit.text(), numeric=False))
        self.seconds_edit = QLineEdit()
        self.rounds_edit = QLineEdit()
        self.between_edit = QLineEdit()
        self.seconds_edit.editingFinished.connect(
            lambda: self._commit_ex_opt("seconds", self.seconds_edit.text(), numeric=True))
        self.rounds_edit.editingFinished.connect(
            lambda: self._commit_ex_opt("rounds", self.rounds_edit.text(), numeric=True))
        self.between_edit.editingFinished.connect(
            lambda: self._commit_ex_opt("between_round_rest_seconds", self.between_edit.text(), numeric=True))
        detail_form.addRow("type", self.type_edit)
        detail_form.addRow("seconds", self.seconds_edit)
        detail_form.addRow("rounds", self.rounds_edit)
        detail_form.addRow("between_round_rest_seconds", self.between_edit)
        ex_layout.addWidget(detail)
        right_layout.addWidget(ex_group, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 760])

        bottom = QHBoxLayout()
        reload_btn = QPushButton("Reload from disk")
        reload_btn.clicked.connect(self.reload_from_disk)
        save_btn = QPushButton("Save templates")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save)
        self.status_label = _muted_label("")
        bottom.addWidget(reload_btn)
        bottom.addStretch()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(save_btn)
        root.addLayout(bottom)

        self._load_from_disk()

    # -- load / template list ------------------------------------------------
    def _load_from_disk(self) -> None:
        raw: Dict[str, dict] = {}
        if self.store.workout_templates_path.exists():
            try:
                loaded = ht.read_json(self.store.workout_templates_path)
                if isinstance(loaded, dict):
                    for name, tpl in loaded.items():
                        if isinstance(tpl, dict):
                            tpl.setdefault("exercises", [])
                            if not isinstance(tpl["exercises"], list):
                                tpl["exercises"] = []
                            raw[str(name)] = tpl
            except Exception as exc:
                QMessageBox.warning(self, APP_TITLE,
                                    f"Could not read workout_templates.json:\n{exc}")
        self.templates = raw
        self.names = list(raw.keys())
        self._populate_template_list()

    def _populate_template_list(self) -> None:
        self._loading = True
        self._current_index = -1
        self.template_list.clear()
        for name in self.names:
            self.template_list.addItem(QListWidgetItem(name))
        self._loading = False
        if self.names:
            self.template_list.setCurrentRow(0)
        else:
            self._clear_right()

    def _current_template(self) -> Optional[dict]:
        if 0 <= self._current_index < len(self.names):
            return self.templates[self.names[self._current_index]]
        return None

    def _on_template_changed(self, row: int) -> None:
        # Commit meta edits into the previously-selected template first.
        if not self._loading:
            self._commit_meta(self._current_index)
        self._current_index = row
        tpl = self._current_template()
        if tpl is None:
            self._clear_right()
            return
        self.exercises = tpl["exercises"]
        self._load_template_into_widgets(tpl)

    def _load_template_into_widgets(self, tpl: dict) -> None:
        self._loading = True
        self.rest_edit.setText(ht.format_number(tpl.get("_default_rest_seconds", 75)))
        self.warmup_edit.setPlainText(str(tpl.get("_warmup_notes", "")))
        self.last_completed_edit.setText(str(tpl.get("_last_completed", "")))
        self._populate_table()
        self._loading = False
        self._load_exercise_detail()

    def _clear_right(self) -> None:
        self._loading = True
        self.exercises = []
        self.rest_edit.clear()
        self.warmup_edit.clear()
        self.last_completed_edit.clear()
        self.table.setRowCount(0)
        self._loading = False
        self._load_exercise_detail()

    # -- meta binding (writes into a specific template index) ----------------
    def _commit_meta(self, index: int) -> None:
        if not (0 <= index < len(self.names)):
            return
        tpl = self.templates[self.names[index]]
        tpl["_default_rest_seconds"] = _num(self.rest_edit.text(), 75)
        warmup = self.warmup_edit.toPlainText()
        if warmup.strip():
            tpl["_warmup_notes"] = warmup
        else:
            tpl.pop("_warmup_notes", None)
        last = self.last_completed_edit.text().strip()
        if last:
            tpl["_last_completed"] = last
        else:
            tpl.pop("_last_completed", None)

    def _set_meta_num(self, key: str, edit: QLineEdit, default: float) -> None:
        if self._loading:
            return
        tpl = self._current_template()
        if tpl is None:
            return
        number = _num(edit.text(), default)
        tpl[key] = number
        self._loading = True
        edit.setText(ht.format_number(number))
        self._loading = False

    def _on_warmup_changed(self) -> None:
        if self._loading:
            return
        tpl = self._current_template()
        if tpl is None:
            return
        text = self.warmup_edit.toPlainText()
        if text.strip():
            tpl["_warmup_notes"] = text
        else:
            tpl.pop("_warmup_notes", None)

    def _commit_last_completed(self) -> None:
        if self._loading:
            return
        tpl = self._current_template()
        if tpl is None:
            return
        text = self.last_completed_edit.text().strip()
        if text:
            tpl["_last_completed"] = text
        else:
            tpl.pop("_last_completed", None)

    # -- template actions ----------------------------------------------------
    def _add_template_named(self, name: str, payload: dict) -> None:
        self.templates[name] = payload
        self.names.append(name)
        self.template_list.addItem(QListWidgetItem(name))
        self.template_list.setCurrentRow(len(self.names) - 1)

    def add_template(self) -> None:
        name = self._ask_unique_name("New template", "Template name:")
        if name is None:
            return
        self._commit_meta(self._current_index)
        self._add_template_named(name, {"_default_rest_seconds": 75, "_warmup_notes": "", "exercises": []})

    def rename_template(self) -> None:
        if self._current_index < 0:
            return
        index = self._current_index
        old = self.names[index]
        new = self._ask_unique_name("Rename template", "New name:", initial=old)
        if new is None or new == old:
            return
        self._commit_meta(index)
        # Rebuild the dict preserving order, with the key at `index` renamed.
        rebuilt: Dict[str, dict] = {}
        for i, name in enumerate(self.names):
            if i == index:
                rebuilt[new] = self.templates[old]
            else:
                rebuilt[name] = self.templates[name]
        self.templates = rebuilt
        self.names[index] = new
        self._loading = True
        item = self.template_list.item(index)
        if item is not None:
            item.setText(new)
        self._loading = False

    def duplicate_template(self) -> None:
        if self._current_index < 0:
            return
        self._commit_meta(self._current_index)
        src = self.names[self._current_index]
        new = self._unique_name(f"{src} (copy)")
        self._add_template_named(new, copy.deepcopy(self.templates[src]))

    def delete_template(self) -> None:
        if self._current_index < 0:
            return
        name = self.names[self._current_index]
        if QMessageBox.question(
            self, APP_TITLE,
            f"Delete template '{name}'?\nThis only takes effect when you click Save templates.",
        ) != QMessageBox.StandardButton.Yes:
            return
        index = self._current_index
        self._current_index = -1
        del self.templates[name]
        del self.names[index]
        self._loading = True
        self.template_list.takeItem(index)
        self.template_list.setCurrentRow(-1)
        self._loading = False
        if self.names:
            self.template_list.setCurrentRow(min(index, len(self.names) - 1))
        else:
            self._clear_right()

    def _ask_unique_name(self, title: str, prompt: str, initial: str = "") -> Optional[str]:
        text, ok = QInputDialog.getText(self, title, prompt, text=initial)
        if not ok:
            return None
        name = text.strip()
        if not name:
            return None
        if name != initial and name in self.templates:
            QMessageBox.warning(self, APP_TITLE, f"A template named '{name}' already exists.")
            return None
        return name

    def _unique_name(self, base: str) -> str:
        name = base
        counter = 2
        while name in self.templates:
            name = f"{base} {counter}"
            counter += 1
        return name

    # -- exercise table ------------------------------------------------------
    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for ex in self.exercises:
            self._append_table_row(ex)

    def _append_table_row(self, ex: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, (_, key) in enumerate(_WORKOUT_COLUMNS):
            self.table.setItem(row, col, QTableWidgetItem(str(ex.get(key, ""))))

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._loading or not (0 <= row < len(self.exercises)):
            return
        cell = self.table.item(row, col)
        if cell is None:
            return
        _, key = _WORKOUT_COLUMNS[col]
        self.exercises[row][key] = cell.text()

    def _on_exercise_row_changed(self, row: int, col: int, prev_row: int, prev_col: int) -> None:
        if row != prev_row:
            self._load_exercise_detail()

    def _selected_exercise(self) -> Optional[dict]:
        row = self.table.currentRow()
        if 0 <= row < len(self.exercises):
            return self.exercises[row]
        return None

    def _load_exercise_detail(self) -> None:
        ex = self._selected_exercise()
        self._loading = True
        enabled = ex is not None
        for widget in (self.no_rir_check, self.type_edit, self.seconds_edit, self.rounds_edit, self.between_edit):
            widget.setEnabled(enabled)
        self.no_rir_check.setChecked(bool(ex.get("no_rir", False)) if ex else False)
        self.type_edit.setText(str(ex.get("type", "")) if ex else "")
        self.seconds_edit.setText(ht.format_number(ex.get("seconds", "")) if ex and "seconds" in ex else "")
        self.rounds_edit.setText(ht.format_number(ex.get("rounds", "")) if ex and "rounds" in ex else "")
        self.between_edit.setText(
            ht.format_number(ex.get("between_round_rest_seconds", "")) if ex and "between_round_rest_seconds" in ex else "")
        self._loading = False

    def _commit_no_rir(self, checked: bool) -> None:
        if self._loading:
            return
        ex = self._selected_exercise()
        if ex is None:
            return
        if checked:
            ex["no_rir"] = True
        else:
            ex.pop("no_rir", None)

    def _commit_ex_opt(self, key: str, value: str, numeric: bool) -> None:
        if self._loading:
            return
        ex = self._selected_exercise()
        if ex is None:
            return
        value = value.strip()
        if not value:
            ex.pop(key, None)
        elif numeric:
            ex[key] = _num(value, 0)
        else:
            ex[key] = value

    # -- exercise actions ----------------------------------------------------
    def _select_ex_row(self, row: int) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.setCurrentCell(row, 0)

    def add_exercise(self) -> None:
        if self._current_template() is None:
            return
        ex = {"name": "New exercise", "sets_reps": "", "target_load": "", "notes": ""}
        self.exercises.append(ex)
        self._loading = True
        self._append_table_row(ex)
        self._loading = False
        self._select_ex_row(len(self.exercises) - 1)

    def duplicate_exercise(self) -> None:
        ex = self._selected_exercise()
        if ex is None:
            return
        index = self.table.currentRow() + 1
        self.exercises.insert(index, copy.deepcopy(ex))
        self._reload_table_keep_selection(index)

    def delete_exercise(self) -> None:
        row = self.table.currentRow()
        ex = self._selected_exercise()
        if ex is None:
            return
        if QMessageBox.question(
            self, APP_TITLE,
            f"Delete exercise '{ex.get('name', 'this exercise')}'?\n"
            "This only takes effect when you click Save templates.",
        ) != QMessageBox.StandardButton.Yes:
            return
        del self.exercises[row]
        self._reload_table_keep_selection(min(row, len(self.exercises) - 1))

    def move_up(self) -> None:
        self._move(-1)

    def move_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        row = self.table.currentRow()
        target = row + delta
        if not (0 <= row < len(self.exercises) and 0 <= target < len(self.exercises)):
            return
        self.exercises[row], self.exercises[target] = self.exercises[target], self.exercises[row]
        self._reload_table_keep_selection(target)

    def _reload_table_keep_selection(self, row: int) -> None:
        self._loading = True
        self._populate_table()
        self._loading = False
        self._select_ex_row(row)
        self._load_exercise_detail()

    # -- reload / save -------------------------------------------------------
    def reload_from_disk(self) -> None:
        if self.names and QMessageBox.question(
            self, APP_TITLE,
            "Reload workout_templates.json from disk? Unsaved edits here will be lost.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self._load_from_disk()
        self.status_label.setText("Reloaded from disk.")

    def save(self) -> None:
        self._commit_meta(self._current_index)
        ordered = {name: self.templates[name] for name in self.names}
        backup = backup_then_write(self.store, self.store.workout_templates_path, ordered)
        where = f" (backup: {backup.name})" if backup else ""
        self.status_label.setText(
            f"Saved workout_templates.json{where}. {RELOAD_REMINDER}")


# ---------------------------------------------------------------------------
# Reusable factory - used both by the standalone launcher below AND by
# health_tracker.py, which lazily imports this to embed the editors as an
# in-app "Config Editor" tab. Keep the editor pages here as the single source
# of truth; the main app just calls this.
# ---------------------------------------------------------------------------
def make_editor_tabs(store: "ht.UnifiedStore", include_recipes: bool = False) -> QTabWidget:
    """Build the nested editor tab widget (Foods / Diet Configs / Workout
    Templates). Set ``include_recipes=True`` only for the standalone app - the
    main app already has its own Recipes tab."""
    tabs = QTabWidget()
    tabs.addTab(FoodsEditorPage(store), "Foods")
    tabs.addTab(DietConfigEditorPage(store), "Diet Configs")
    tabs.addTab(WorkoutTemplateEditorPage(store), "Workout Templates")
    if include_recipes:
        # Recipes already has a full CRUD editor in the main app; reuse it.
        tabs.addTab(ht.RecipesPage(store), "Recipes")
    return tabs


# ---------------------------------------------------------------------------
# Standalone launcher (run `python config_editor.py` for a separate editor
# window). The same pages are also available inside the main app.
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, store: "ht.UnifiedStore"):
        super().__init__()
        self.store = store
        self.setWindowTitle(f"{APP_TITLE} - {store.data_dir}")
        self.resize(1250, 865)
        self.setCentralWidget(make_editor_tabs(store, include_recipes=True))
        self.statusBar().showMessage(f"Editing data in: {store.data_dir}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyleSheet(APP_QSS)
    ht.apply_app_icon(app)

    store = ht.UnifiedStore(ht.get_app_dir())

    window = MainWindow(store)
    ht.apply_app_icon(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
