"""The main updater window and all of its interaction logic."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wsu.core.config import (
    APP_TITLE,
    ENABLE_FILESIZE_SCAN,
    ICON_FILENAME,
    WINGET_TIMEOUT_SECONDS,
)
from wsu.core.logging_config import get_logger
from wsu.core.models import UpdateItem
from wsu.core.paths import (
    EXCLUDED_UPDATES_FILE,
    FAKE_UPDATES_FILE,
    SKIPPED_UPDATES_FILE,
    resolve_data_path,
    resource_path,
)
from wsu.core.storage import load_json, save_json
from wsu.ui.icons import build_logo_pixmap
from wsu.ui.widgets import (
    EmptyStateWidget,
    FooterProxy,
    SearchBar,
    StatusChip,
    TitleBar,
    VersionBadge,
)
from wsu.workers import ExclusionsWorker, ScanWorker, UpdateWorker

_log = get_logger("ui")


class MainWindow(QMainWindow):
    """Top-level window orchestrating scanning, updating, and exclusions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1100, 680)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        icon_path = resource_path(ICON_FILENAME)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.fake_updates_path = resolve_data_path(FAKE_UPDATES_FILE)
        self.excluded_updates_path = resolve_data_path(EXCLUDED_UPDATES_FILE)
        self.skipped_updates_path = resolve_data_path(SKIPPED_UPDATES_FILE)

        self.fake_updates: Dict[str, str] = load_json(self.fake_updates_path)
        self.excluded_updates: Dict[str, bool] = load_json(self.excluded_updates_path)
        self.skipped_updates: Dict[str, str] = load_json(self.skipped_updates_path)

        self.update_in_progress = False
        self.updates: List[UpdateItem] = []
        self.updates_by_id: Dict[str, UpdateItem] = {}
        self._current_thread: Optional[QThread] = None
        self.scan_in_progress = False
        self._update_total = 0
        self._update_done = 0

        self._scan_watchdog = QTimer(self)
        self._scan_watchdog.setSingleShot(True)
        self._scan_watchdog.timeout.connect(self._handle_scan_timeout)

        self._build_ui()
        self._setup_tray()
        self._show_empty_state("idle")

        QTimer.singleShot(300, self.check_for_updates)

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 8, 10, 10)
        root_layout.setSpacing(8)

        self.title_bar = TitleBar(self)
        root_layout.addWidget(self.title_bar)

        self.shell = QFrame()
        self.shell.setObjectName("Shell")
        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(18, 14, 18, 16)
        shell_layout.setSpacing(12)
        root_layout.addWidget(self.shell, 1)

        shell_layout.addWidget(self._build_header())

        header_divider = QFrame()
        header_divider.setObjectName("HeaderDivider")
        header_divider.setFrameShape(QFrame.Shape.HLine)
        header_divider.setFixedHeight(1)
        shell_layout.addWidget(header_divider)

        shell_layout.addWidget(self._build_search_row())

        self.stack = QStackedWidget()
        shell_layout.addWidget(self.stack, 1)
        self._build_stack_pages()

        shell_layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        info_block = QVBoxLayout()
        info_block.setContentsMargins(0, 0, 0, 0)
        info_block.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        self.section_title = QLabel("Update Center")
        self.section_title.setObjectName("SectionTitle")
        self.badge_label = QLabel("0")
        self.badge_label.setObjectName("UpdateBadge")
        self.badge_label.setVisible(False)
        title_row.addWidget(self.section_title)
        title_row.addWidget(self.badge_label)
        title_row.addStretch(1)

        self.status_label = QLabel("Ready to scan for updates")
        self.status_label.setObjectName("StatusText")
        info_block.addLayout(title_row)
        info_block.addWidget(self.status_label)
        header_layout.addLayout(info_block)
        header_layout.addStretch(1)

        self.check_button = self._make_button("Check for Updates", True)
        self.update_all_button = self._make_button("Update All", False)
        self.update_selected_button = self._make_button("Update Selected", False)
        self.manage_exclusions_button = self._make_button("Manage Exclusions", False)

        for btn in (
            self.check_button,
            self.update_all_button,
            self.update_selected_button,
            self.manage_exclusions_button,
        ):
            header_layout.addWidget(btn)

        self.check_button.clicked.connect(self.check_for_updates)
        self.update_all_button.clicked.connect(self.update_all)
        self.update_selected_button.clicked.connect(self.update_selected)
        self.manage_exclusions_button.clicked.connect(self.toggle_exclusions_view)

        self.check_button.setToolTip("Scan for available software updates via winget")
        self.update_all_button.setToolTip("Update all packages in the list")
        self.update_selected_button.setToolTip("Update only the selected rows")
        self.manage_exclusions_button.setToolTip(
            "View and manage permanently excluded packages"
        )
        return header

    def _build_search_row(self) -> QWidget:
        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(12)
        self._search_bar = SearchBar("Search app name or package id")
        self.search_input = self._search_bar.line_edit
        self.search_input.textChanged.connect(self.apply_filter)
        search_layout.addWidget(self._search_bar, 1)
        self.result_counter = QLabel("0 updates")
        self.result_counter.setObjectName("CounterText")
        search_layout.addWidget(self.result_counter)
        return search_row

    def _build_stack_pages(self) -> None:
        # -- Updates page --
        self.updates_view = QWidget()
        updates_layout = QVBoxLayout(self.updates_view)
        updates_layout.setContentsMargins(0, 0, 0, 0)
        updates_layout.setSpacing(10)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Software", "Installed", "Available", "Size", "Update", "Exclude", "Skip"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        for action_col in (4, 5, 6):
            header.setSectionResizeMode(action_col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(action_col, 92)
        self.table.itemSelectionChanged.connect(self.update_selected_state)
        updates_layout.addWidget(self.table)
        self.stack.addWidget(self.updates_view)

        # -- Empty state page --
        self.empty_state = EmptyStateWidget()
        self.stack.addWidget(self.empty_state)

        # -- Exclusions page --
        self.exclusions_view = QWidget()
        exclusions_layout = QVBoxLayout(self.exclusions_view)
        exclusions_layout.setContentsMargins(0, 0, 0, 0)
        exclusions_layout.setSpacing(12)
        self.exclusions_hint = QLabel(
            "Excluded apps are hidden from the updates list. "
            "Click Unexclude to restore them."
        )
        self.exclusions_hint.setObjectName("HintText")
        exclusions_layout.addWidget(self.exclusions_hint)
        self.exclusions_table = QTableWidget(0, 2)
        self.exclusions_table.setHorizontalHeaderLabels(["Software", "Action"])
        self.exclusions_table.verticalHeader().setVisible(False)
        self.exclusions_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.exclusions_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.exclusions_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        ex_header = self.exclusions_table.horizontalHeader()
        ex_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ex_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        exclusions_layout.addWidget(self.exclusions_table)
        self.stack.addWidget(self.exclusions_view)

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        footer_layout.addWidget(self.progress, 1)
        self.footer_status_chip = StatusChip()
        footer_layout.addWidget(self.footer_status_chip)
        self.footer_status = FooterProxy(self.footer_status_chip)
        self.size_grip = QSizeGrip(self)
        footer_layout.addWidget(self.size_grip)
        return footer

    # -- Tray ---------------------------------------------------------------

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        icon = self.windowIcon()
        if icon.isNull():
            icon = QIcon(build_logo_pixmap(32))
        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.show_normal)
        check_action = QAction("Check for Updates", self)
        check_action.triggered.connect(self.check_for_updates)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(open_action)
        menu.addAction(check_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._handle_tray_activate)
        self.tray.show()

    def _handle_tray_activate(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_normal()

    def show_normal(self) -> None:
        """Restore and focus the window from the tray."""
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_maximize(self) -> None:
        """Toggle between maximised and normal window states."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # -- Small UI helpers ---------------------------------------------------

    def _make_button(self, text: str, primary: bool) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("PrimaryButton" if primary else "GhostButton")
        return btn

    def _make_table_button(self, text: str, obj_name: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setObjectName(obj_name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setMinimumWidth(76)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return btn

    def _show_empty_state(self, state: str) -> None:
        self.empty_state.set_state(state)
        self.stack.setCurrentWidget(self.empty_state)

    def _show_updates_view(self) -> None:
        self.stack.setCurrentWidget(self.updates_view)

    def _update_badge(self) -> None:
        count = len(self.updates)
        self.badge_label.setText(str(count))
        self.badge_label.setVisible(count > 0)

    def apply_filter(self) -> None:
        """Hide table rows that do not match the current search query."""
        query = self.search_input.text().strip().lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            package_id = (
                name_item.data(Qt.ItemDataRole.UserRole) if name_item else ""
            )
            name = name_item.text().lower() if name_item else ""
            match = query in name or (package_id and query in package_id.lower())
            self.table.setRowHidden(row, not match)

    def update_selected_state(self) -> None:
        """Enable/disable the 'Update Selected' button based on selection."""
        if self.update_in_progress:
            self.update_selected_button.setEnabled(False)
            return
        selected = bool(self.table.selectionModel().selectedRows())
        self.update_selected_button.setEnabled(selected and bool(self.updates))

    def toggle_exclusions_view(self) -> None:
        """Switch between the updates list and the exclusions manager."""
        if self.stack.currentWidget() == self.updates_view:
            self.stack.setCurrentWidget(self.exclusions_view)
            self.manage_exclusions_button.setText("Back to Updates")
            self.load_exclusions()
        else:
            if self.updates:
                self._show_updates_view()
            else:
                self._show_empty_state("up_to_date")
            self.manage_exclusions_button.setText("Manage Exclusions")
            self.status_label.setText(
                f"Found {len(self.updates)} update(s)"
                if self.updates
                else "Ready to scan for updates"
            )

    def lock_controls(self) -> None:
        """Disable all action buttons during a scan or update."""
        self.check_button.setEnabled(False)
        self.update_all_button.setEnabled(False)
        self.update_selected_button.setEnabled(False)
        self.manage_exclusions_button.setEnabled(False)

    def unlock_controls(self) -> None:
        """Re-enable action buttons appropriate to the current state."""
        self.check_button.setEnabled(True)
        self.manage_exclusions_button.setEnabled(True)
        self.update_all_button.setEnabled(bool(self.updates))
        self.update_selected_button.setEnabled(
            bool(self.updates)
            and bool(self.table.selectionModel().selectedRows())
        )

    # -- Scanning -----------------------------------------------------------

    def _start_scan_watchdog(self) -> None:
        self._scan_watchdog.stop()
        self._scan_watchdog.start((WINGET_TIMEOUT_SECONDS * 1000) + 2000)

    def _stop_scan_watchdog(self) -> None:
        if self._scan_watchdog.isActive():
            self._scan_watchdog.stop()

    def _finish_scan(self) -> None:
        self.scan_in_progress = False
        self._stop_scan_watchdog()

    def _handle_scan_timeout(self) -> None:
        if not self.scan_in_progress:
            return
        self.scan_in_progress = False
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.footer_status.setText("Idle")
        self.status_label.setText("Scan timed out")
        self._show_empty_state("idle")
        self.unlock_controls()
        QMessageBox.critical(
            self, "Error", f"winget timed out after {WINGET_TIMEOUT_SECONDS} seconds"
        )

    def check_for_updates(self) -> None:
        """Kick off a background scan for available updates."""
        if self.update_in_progress:
            QMessageBox.warning(self, "Warning", "An update is already in progress")
            return
        if self.scan_in_progress:
            QMessageBox.information(self, "Info", "A scan is already in progress")
            return
        self.scan_in_progress = True
        self._start_scan_watchdog()
        self.status_label.setText("Checking for updates...")
        self.footer_status.setText("Scanning winget catalog")
        self.progress.setRange(0, 0)
        self.lock_controls()
        self._show_empty_state("scanning")
        self.table.setRowCount(0)
        self.updates.clear()
        self.updates_by_id.clear()
        self.result_counter.setText("0 updates")

        worker = ScanWorker(
            self.fake_updates, self.excluded_updates, self.skipped_updates
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(self._handle_scan_results)
        worker.size_ready.connect(self._handle_size_ready)
        worker.error.connect(self._handle_scan_error)
        worker.finished.connect(self._finish_scan)
        worker.finished.connect(self._handle_scan_thread_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._current_thread = thread
        self._scan_worker = worker  # retain so it is not garbage collected
        thread.start()

    def _handle_scan_error(self, message: str) -> None:
        self._finish_scan()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.footer_status.setText("Idle")
        self.status_label.setText("Error occurred")
        self._show_empty_state("idle")
        self.unlock_controls()
        QMessageBox.critical(self, "Error", message)

    def _handle_scan_results(
        self,
        updates: List[UpdateItem],
        new_skipped: Dict[str, str],
        skipped_changed: bool,
    ) -> None:
        self._finish_scan()
        self.updates = updates
        self.updates_by_id = {u.package_id: u for u in updates}
        if skipped_changed:
            try:
                save_json(self.skipped_updates_path, new_skipped)
                self.skipped_updates = new_skipped
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Warning", str(exc))
        self.render_updates()
        if updates:
            self._show_updates_view()
            self.status_label.setText(f"Found {len(updates)} update(s)")
            if self.tray:
                self.tray.showMessage(
                    "Updates available",
                    f"{len(updates)} update(s) ready to install.",
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )
        else:
            self._show_empty_state("up_to_date")
            self.status_label.setText("No updates available")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        if updates and ENABLE_FILESIZE_SCAN:
            self.footer_status.setText("Fetching download sizes")
        else:
            self.footer_status.setText("Idle")
        self.unlock_controls()
        self.result_counter.setText(f"{len(updates)} updates")

    def _handle_size_ready(self, package_id: str, size: float) -> None:
        update = self.updates_by_id.get(package_id)
        if update is None:
            return
        update.file_size = size
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == package_id:
                self.table.setItem(row, 3, QTableWidgetItem(f"{size} MB"))
                break

    def _handle_scan_thread_finished(self) -> None:
        # Phase 2 (size fetching) is done; return the footer to idle.
        if not self.scan_in_progress:
            self.footer_status.setText("Idle")

    def render_updates(self) -> None:
        """Rebuild the updates table from :attr:`updates`."""
        self.table.setRowCount(0)
        for update in self.updates:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(update.name)
            name_item.setData(Qt.ItemDataRole.UserRole, update.package_id)
            self.table.setItem(row, 0, name_item)

            installed_badge = VersionBadge(update.installed_version, variant="installed")
            self.table.setCellWidget(row, 1, installed_badge)
            available_badge = VersionBadge(update.available_version, variant="available")
            self.table.setCellWidget(row, 2, available_badge)

            if update.file_size is not None:
                size_text = f"{update.file_size} MB"
            elif ENABLE_FILESIZE_SCAN:
                size_text = "…"
            else:
                size_text = "N/A"
            self.table.setItem(row, 3, QTableWidgetItem(size_text))

            update_btn = self._make_table_button("Update", "ActionUpdateButton")
            update_btn.setToolTip(
                f"Update {update.name} to {update.available_version}"
            )
            update_btn.clicked.connect(
                lambda _, pid=update.package_id: self.update_single(pid)
            )
            self.table.setCellWidget(row, 4, update_btn)

            exclude_btn = self._make_table_button("Exclude", "ActionExcludeButton")
            exclude_btn.setToolTip(f"Permanently exclude {update.name} from updates")
            exclude_btn.clicked.connect(
                lambda _, pid=update.package_id: self.exclude_package(pid)
            )
            self.table.setCellWidget(row, 5, exclude_btn)

            skip_btn = self._make_table_button("Skip", "ActionSkipButton")
            skip_btn.setToolTip(
                f"Skip version {update.available_version} of {update.name}"
            )
            skip_btn.clicked.connect(
                lambda _, pid=update.package_id: self.skip_version(pid)
            )
            self.table.setCellWidget(row, 6, skip_btn)

            self.table.setRowHeight(row, 40)

        self.apply_filter()
        self.result_counter.setText(f"{len(self.updates)} updates")
        self.update_selected_state()
        self._update_badge()

    # -- Updating -----------------------------------------------------------

    def update_single(self, package_id: str) -> None:
        """Confirm and update a single package by id."""
        if self.update_in_progress:
            QMessageBox.warning(self, "Warning", "An update is already in progress")
            return
        update = self.updates_by_id.get(package_id)
        if not update:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"Update {update.name} to version {update.available_version}?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.start_update([package_id], f"Updating {update.name}...")

    def update_selected(self) -> None:
        """Confirm and update all currently selected rows."""
        if self.update_in_progress:
            QMessageBox.warning(self, "Warning", "An update is already in progress")
            return
        selected = [
            self.table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole)
            for row in self.table.selectionModel().selectedRows()
        ]
        if not selected:
            QMessageBox.information(self, "Info", "No software selected for update")
            return
        reply = QMessageBox.question(
            self, "Confirm Update", f"Update {len(selected)} selected package(s)?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.start_update(selected, "Updating selected software...")

    def update_all(self) -> None:
        """Confirm and update every package in the list."""
        if self.update_in_progress:
            QMessageBox.warning(self, "Warning", "An update is already in progress")
            return
        if not self.updates:
            QMessageBox.information(self, "Info", "No updates available")
            return
        reply = QMessageBox.question(
            self, "Confirm Update", f"Update all {len(self.updates)} package(s)?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        package_ids = [u.package_id for u in self.updates]
        self.start_update(package_ids, "Updating all software...")

    def start_update(self, package_ids: List[str], status_text: str) -> None:
        """Begin a background update of the given packages."""
        self.update_in_progress = True
        self._update_total = len(package_ids)
        self._update_done = 0
        self.status_label.setText(status_text)
        self.footer_status.setText("Updating packages")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.lock_controls()

        worker = UpdateWorker(package_ids, self.updates_by_id)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._handle_update_progress)
        worker.package_progress.connect(self._handle_package_progress)
        worker.item_complete.connect(self._handle_item_complete)
        worker.error.connect(self._handle_update_error)
        worker.finished.connect(self._handle_update_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._current_thread = thread
        self._update_worker = worker  # retain so it is not garbage collected
        thread.start()

    def _handle_package_progress(self, package_id: str, percent: int) -> None:
        # Combine the current package's live percent with overall completion so
        # the bar reflects real winget download/install progress end to end.
        total = max(1, self._update_total)
        overall = int((self._update_done + percent / 100.0) / total * 100)
        self.progress.setValue(max(0, min(100, overall)))
        update = self.updates_by_id.get(package_id)
        name = update.name if update else package_id
        self.status_label.setText(f"Updating {name}… {percent}%")
        self.footer_status.setText(
            f"Updating {name} ({self._update_done + 1}/{total}) — {percent}%"
        )

    def _handle_update_progress(self, index: int, total: int, package_id: str) -> None:
        self._update_done = index
        self.progress.setValue(int(index / max(1, total) * 100))
        update = self.updates_by_id.get(package_id)
        if update:
            self.footer_status.setText(f"Updated {update.name} ({index}/{total})")

    def _handle_item_complete(
        self, package_id: str, success: bool, fake_update: bool, message: str
    ) -> None:
        if fake_update:
            update = self.updates_by_id.get(package_id)
            if update:
                self.fake_updates[package_id] = update.available_version
                try:
                    save_json(self.fake_updates_path, self.fake_updates)
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.warning(self, "Warning", str(exc))
            self.remove_update(package_id)
            return
        if success:
            update = self.updates_by_id.get(package_id)
            self.remove_update(package_id)
            if update and self.tray:
                self.tray.showMessage(
                    "Update complete",
                    f"{update.name} updated successfully.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )

    def _handle_update_error(self, message: str) -> None:
        QMessageBox.critical(self, "Update Error", message)

    def _handle_update_finished(self, success: bool) -> None:
        self.update_in_progress = False
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.footer_status.setText("Idle")
        if success:
            if not self.updates:
                self.status_label.setText("All updates completed")
                QMessageBox.information(
                    self, "Success", "All updates completed successfully"
                )
            else:
                self.status_label.setText(f"Found {len(self.updates)} update(s)")
        else:
            self.status_label.setText("Update failed")
        self.unlock_controls()
        self.update_selected_state()
        self._update_badge()

    def remove_update(self, package_id: str) -> None:
        """Remove a package from the list and table after it is resolved."""
        row_to_remove = None
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == package_id:
                row_to_remove = row
                break
        if row_to_remove is not None:
            self.table.removeRow(row_to_remove)
        self.updates = [u for u in self.updates if u.package_id != package_id]
        self.updates_by_id.pop(package_id, None)
        self.result_counter.setText(f"{len(self.updates)} updates")
        self._update_badge()
        if not self.updates:
            self.status_label.setText("No updates available")
            self._show_empty_state("up_to_date")

    # -- Exclusions & skips -------------------------------------------------

    def exclude_package(self, package_id: str) -> None:
        """Permanently exclude a package from future scans."""
        if package_id in self.excluded_updates:
            return
        update = self.updates_by_id.get(package_id)
        if not update:
            return
        reply = QMessageBox.question(
            self, "Confirm Exclusion", f"Exclude updates for {update.name} permanently?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.excluded_updates[package_id] = True
            save_json(self.excluded_updates_path, self.excluded_updates)
            self.remove_update(package_id)
            self.status_label.setText(f"Excluded {update.name} from updates")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Error excluding package: {exc}")
        self.unlock_controls()

    def skip_version(self, package_id: str) -> None:
        """Skip the currently available version of a package."""
        if self.update_in_progress:
            QMessageBox.warning(self, "Warning", "An update is already in progress")
            return
        update = self.updates_by_id.get(package_id)
        if not update:
            return
        available_version = update.available_version
        if not available_version:
            QMessageBox.information(
                self,
                "Skip Version",
                f"Unable to skip {update.name} because no version information "
                "is available.",
            )
            return
        if self.skipped_updates.get(package_id) == available_version:
            self.remove_update(package_id)
            return
        reply = QMessageBox.question(
            self,
            "Skip This Version",
            f"Skip version {available_version} of {update.name}?\n\n"
            "You will see this software again when a newer version is released.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.skipped_updates[package_id] = available_version
            save_json(self.skipped_updates_path, self.skipped_updates)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Error saving skipped version: {exc}")
            return
        self.remove_update(package_id)
        self.status_label.setText(
            f"Skipped {update.name} (version {available_version})"
        )
        self.unlock_controls()

    def load_exclusions(self) -> None:
        """Load and display the set of excluded packages."""
        self.exclusions_table.setRowCount(0)
        self.status_label.setText("Loading exclusions...")
        worker = ExclusionsWorker(list(self.excluded_updates.keys()))
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(self._render_exclusions)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._current_thread = thread
        self._exclusions_worker = worker  # retain so it is not garbage collected
        thread.start()

    def _render_exclusions(self, entries: List[Tuple[str, str]]) -> None:
        self.exclusions_table.setRowCount(0)
        for package_id, name in entries:
            row = self.exclusions_table.rowCount()
            self.exclusions_table.insertRow(row)
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, package_id)
            self.exclusions_table.setItem(row, 0, name_item)
            action_btn = self._make_table_button("Unexclude", "ActionButton")
            action_btn.clicked.connect(
                lambda _, pid=package_id: self.unexclude(pid)
            )
            self.exclusions_table.setCellWidget(row, 1, action_btn)
            self.exclusions_table.setRowHeight(row, 44)
        if entries:
            self.status_label.setText(f"Manage Exclusions - {len(entries)} item(s)")
        else:
            self.status_label.setText("No excluded packages")

    def unexclude(self, package_id: str) -> None:
        """Restore a previously excluded package and refresh the list."""
        if package_id in self.excluded_updates:
            try:
                self.excluded_updates.pop(package_id, None)
                save_json(self.excluded_updates_path, self.excluded_updates)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", f"Error saving exclusions: {exc}")
                return
        self.load_exclusions()

    # -- Lifecycle ----------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self.tray:
            self.tray.hide()
        event.accept()
