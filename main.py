"""
PyQt6-based Windows software updater GUI.

This application wraps Windows Package Manager (winget) to scan for
available updates, apply them, and manage exclusions or skipped versions.
It provides a custom, frameless dark UI with a minimal abstract logo and
system tray notifications.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from PyQt6.QtCore import (
    Qt,
    QObject,
    QThread,
    pyqtSignal,
    QTimer,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

APP_TITLE = "Windows Software Updater"
APP_SUBTITLE = "Powered by Windows Package Manager (winget)"

WINGET_TIMEOUT_SECONDS = int(os.environ.get("WSU_WINGET_TIMEOUT", "120"))
WINGET_SHOW_TIMEOUT_SECONDS = int(os.environ.get("WSU_WINGET_SHOW_TIMEOUT", "20"))
WINGET_REQUIRED_FLAGS = ["--accept-source-agreements"]
WINGET_OPTIONAL_FLAGS = []
if os.environ.get("WSU_WINGET_OPTIONAL_FLAGS", "0") == "1":
    WINGET_OPTIONAL_FLAGS = ["--accept-package-agreements", "--disable-interactivity"]
ENABLE_FILESIZE_SCAN = os.environ.get("WSU_FILESIZE_SCAN", "1") == "1"
ENABLE_EXECUTABLE_SCAN = os.environ.get("WSU_EXECUTABLE_SCAN", "0") == "1"

ACCENT = "#21D4FD"
ACCENT_SOFT = "#9BE8FF"
BG = "#0B0C0F"
PANEL = "#111216"
PANEL_BORDER = "#1C1F26"
TEXT = "#E7EAF0"
TEXT_MUTED = "#A8B0BF"
SUCCESS = "#2BD98A"
WARNING = "#F0C84B"
ERROR = "#FF5C5C"

# --- Extended surface & interaction tokens ---
SURFACE = "#0F1116"        # table / input background
SURFACE_2 = "#12161C"      # alternating rows
HOVER = "#161C26"          # row hover
BUTTON_BG = "#161A20"      # ghost / action button fill
BORDER_SOFT = "#252A36"    # subtle border
BORDER_MID = "#2A3040"     # scrollbar handle, separator
BORDER_FOCUS = "#21D4FD"   # focused ring
WARN_BORDER = "#F0C84B"    # exclude button border
MUTED_BORDER = "#2A313D"   # skip button border
TITLE_BG_1 = "#10141B"     # title bar gradient start
TITLE_BG_2 = "#141A22"     # title bar gradient end


def resolve_data_path(filename: str) -> str:
    """Resolve a stable data path with backward-compatible fallbacks."""
    cwd_path = os.path.join(os.getcwd(), filename)
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    for candidate in (cwd_path, local_path):
        if os.path.exists(candidate):
            return candidate
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".windows-software-updater")
    app_dir = os.path.join(base, "WindowsSoftwareUpdater")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, filename)


def load_json(path: str) -> Dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_json(path: str, data: Dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
    except IOError as exc:
        raise IOError(f"Error saving JSON file '{path}': {exc}")


@dataclass
class UpdateItem:
    name: str
    package_id: str
    installed_version: str
    available_version: str
    file_size: Optional[float] = None
    executable_path: Optional[str] = None


class WingetClient:
    @staticmethod
    def run_command(args: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        if timeout is None:
            timeout = WINGET_TIMEOUT_SECONDS
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            return subprocess.run(
                args,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"winget timed out after {timeout} seconds") from exc

    @staticmethod
    def run_winget(args: List[str]) -> subprocess.CompletedProcess:
        full_args = args + WINGET_REQUIRED_FLAGS + WINGET_OPTIONAL_FLAGS
        result = WingetClient.run_command(full_args)
        if result.returncode != 0:
            combined = f"{result.stdout} {result.stderr}".lower()
            unknown_tokens = (
                "unknown argument",
                "unrecognized option",
                "not recognized",
                "unknown option",
                "is not a valid option",
            )
            if any(token in combined for token in unknown_tokens):
                result = WingetClient.run_command(args + WINGET_REQUIRED_FLAGS)
        return result

    @staticmethod
    def parse_upgrade_output(output: str) -> List[Tuple[str, str, str, str]]:
        lines = output.splitlines()
        start_index = 0
        for i, line in enumerate(lines):
            if line.startswith("Name") and "Id" in line:
                start_index = i + 1
                break
        entries: List[Tuple[str, str, str, str]] = []
        for line in lines[start_index:]:
            if not line.strip() or line.strip().startswith("-"):
                continue
            cleaned = line.replace("winget", "").strip()
            pattern = r"^(.*?)\s+([^\s]+)\s+([^\s]+\s*(?:\([^\)]+\))?)\s+([^\s]+\s*(?:\([^\)]+\))?)$"
            match = re.match(pattern, cleaned)
            if match:
                name = match.group(1).strip()
                package_id = match.group(2).strip()
                installed_version = match.group(3).strip()
                available_version = match.group(4).strip()
                entries.append((name, package_id, installed_version, available_version))
            else:
                parts = re.split(r"\s{2,}", cleaned)
                if len(parts) >= 4:
                    name = parts[0].strip()
                    package_id = parts[1].strip()
                    installed_version = parts[2].strip()
                    available_version = parts[3].strip()
                    entries.append((name, package_id, installed_version, available_version))
        return entries

    @staticmethod
    def get_file_size(package_id: str) -> Optional[float]:
        if not ENABLE_FILESIZE_SCAN:
            return None
        try:
            result = WingetClient.run_command(
                ["winget", "show", package_id],
                timeout=WINGET_SHOW_TIMEOUT_SECONDS,
            )
            match = re.search(
                r"Installer Url:\s*(https?://[^\s]+)",
                result.stdout or "",
                re.IGNORECASE,
            )
            if not match:
                return None
            link = match.group(1)
            try:
                response = requests.head(link, allow_redirects=True, timeout=6)
                if "Content-Length" not in response.headers:
                    response = requests.get(link, stream=True, timeout=6)
                size_bytes = int(response.headers.get("Content-Length", 0))
                if size_bytes <= 0:
                    return None
                return round(size_bytes / (1024 * 1024), 2)
            except Exception:
                return None
        except Exception:
            return None

    @staticmethod
    def get_executable_path(package_id: str, package_name: str) -> Optional[str]:
        if not ENABLE_EXECUTABLE_SCAN:
            return None
        try:
            result = WingetClient.run_command(
                ["winget", "show", "--id", package_id, "--exact"],
                timeout=WINGET_SHOW_TIMEOUT_SECONDS,
            )
            output = result.stdout or ""
            match = re.search(r"Install Location:\s*(.*?)\n", output, re.IGNORECASE)
            if not match:
                return None
            install_path = match.group(1).strip()
            if not install_path or not os.path.exists(install_path):
                return None
            for root_dir, _, files in os.walk(install_path):
                for file in files:
                    if file.lower().endswith(".exe") and (
                        package_name.lower() in file.lower()
                        or package_id.lower() in file.lower()
                    ):
                        return os.path.join(root_dir, file)
        except Exception:
            return None
        return None

    @staticmethod
    def resolve_package_name(package_id: str) -> str:
        try:
            search_result = WingetClient.run_command(
                ["winget", "search", "--id", package_id, "--exact"]
            )
            output = search_result.stdout or ""
            for line in output.splitlines():
                if package_id in line and not line.strip().startswith(("Name", "--")):
                    match = re.match(
                        rf"^(.*?)\s{{2,}}{re.escape(package_id)}(\s|$)", line
                    )
                    if match:
                        candidate = match.group(1).strip()
                        if candidate:
                            return candidate
            show_result = WingetClient.run_command(
                ["winget", "show", "--id", package_id, "--exact"]
            )
            match = re.search(
                r"^Name:\s*(.+)$",
                show_result.stdout or "",
                re.IGNORECASE | re.MULTILINE,
            )
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return package_id


class ScanWorker(QObject):
    result = pyqtSignal(list, dict, bool)
    size_ready = pyqtSignal(str, float)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        fake_updates: Dict[str, str],
        excluded_updates: Dict[str, bool],
        skipped_updates: Dict[str, str],
    ) -> None:
        super().__init__()
        self.fake_updates = dict(fake_updates)
        self.excluded_updates = dict(excluded_updates)
        self.skipped_updates = dict(skipped_updates)

    def run(self) -> None:
        skipped_changed = False
        updates: List[UpdateItem] = []
        try:
            result = WingetClient.run_winget(["winget", "upgrade"])
            entries = WingetClient.parse_upgrade_output(result.stdout or "")
            for name, package_id, installed_version, available_version in entries:
                if (
                    package_id in self.fake_updates
                    and self.fake_updates[package_id] == available_version
                ) or (package_id in self.excluded_updates):
                    continue
                skip_version = self.skipped_updates.get(package_id)
                if skip_version == available_version:
                    continue
                if skip_version is not None and skip_version != available_version:
                    self.skipped_updates.pop(package_id, None)
                    skipped_changed = True
                updates.append(
                    UpdateItem(
                        name=name,
                        package_id=package_id,
                        installed_version=installed_version,
                        available_version=available_version,
                        file_size=None,
                        executable_path=None,
                    )
                )
            # Phase 1: emit the parsed list immediately so the UI is responsive.
            # The slow per-package metadata lookups must not block "checking".
            self.result.emit(updates, self.skipped_updates, skipped_changed)
            # Phase 2: fetch download sizes in the background and stream them in.
            if ENABLE_FILESIZE_SCAN:
                for item in updates:
                    size = WingetClient.get_file_size(item.package_id)
                    if size is not None:
                        self.size_ready.emit(item.package_id, size)
        except FileNotFoundError:
            self.error.emit("winget not found. Please install Windows Package Manager.")
        except TimeoutError as exc:
            self.error.emit(str(exc))
        except subprocess.CalledProcessError as exc:
            self.error.emit(f"Error checking for updates: {exc.stderr}")
        finally:
            self.finished.emit()


class UpdateWorker(QObject):
    progress = pyqtSignal(int, int, str)
    package_progress = pyqtSignal(str, int)  # package_id, percent (0-100)
    item_complete = pyqtSignal(str, bool, bool, str)
    error = pyqtSignal(str)
    finished = pyqtSignal(bool)

    _PCT_RE = re.compile(r"(\d{1,3})\s*%")
    _UNKNOWN_TOKENS = (
        "unknown argument",
        "unrecognized option",
        "not recognized",
        "unknown option",
        "is not a valid option",
    )

    def __init__(self, package_ids: List[str], updates_by_id: Dict[str, UpdateItem]) -> None:
        super().__init__()
        self.package_ids = list(package_ids)
        self.updates_by_id = dict(updates_by_id)

    def _stream(self, args: List[str], package_id: str) -> Tuple[int, str]:
        """Run winget while streaming stdout so download/install percent can be
        emitted live. Returns (returncode, combined_output_lowercased)."""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(
            args,
            startupinfo=startupinfo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        collected: List[str] = []
        token = ""
        last_pct = -1
        assert proc.stdout is not None
        while True:
            ch = proc.stdout.read(1)
            if not ch:
                break
            # winget repaints progress on the same line using carriage returns.
            if ch in ("\r", "\n"):
                if token.strip():
                    collected.append(token)
                    match = self._PCT_RE.search(token)
                    if match:
                        pct = max(0, min(100, int(match.group(1))))
                        if pct != last_pct:
                            last_pct = pct
                            self.package_progress.emit(package_id, pct)
                token = ""
            else:
                token += ch
        if token.strip():
            collected.append(token)
        proc.wait()
        return proc.returncode, " ".join(collected).lower()

    def run(self) -> None:
        total = len(self.package_ids)
        try:
            for index, package_id in enumerate(self.package_ids, start=1):
                self.package_progress.emit(package_id, 0)
                base = ["winget", "upgrade", package_id]
                returncode, combined = self._stream(
                    base + WINGET_REQUIRED_FLAGS + WINGET_OPTIONAL_FLAGS, package_id
                )
                if returncode != 0 and any(t in combined for t in self._UNKNOWN_TOKENS):
                    # Optional flags rejected by this winget version; retry plainly.
                    returncode, combined = self._stream(
                        base + WINGET_REQUIRED_FLAGS, package_id
                    )
                if returncode == 0 or "successfully upgraded" in combined:
                    self.package_progress.emit(package_id, 100)
                    self.item_complete.emit(package_id, True, False, "")
                else:
                    if "no package found" in combined or "not installed" in combined:
                        self.item_complete.emit(package_id, False, True, "")
                    else:
                        message = combined.strip() or "Unknown error occurred"
                        self.error.emit(f"Error updating {package_id}: {message}")
                        self.finished.emit(False)
                        return
                self.progress.emit(index, total, package_id)
            self.finished.emit(True)
        except FileNotFoundError:
            self.error.emit("winget not found. Please install Windows Package Manager.")
            self.finished.emit(False)
        except TimeoutError as exc:
            self.error.emit(str(exc))
            self.finished.emit(False)
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")
            self.finished.emit(False)


class ExclusionsWorker(QObject):
    result = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, excluded_ids: List[str]) -> None:
        super().__init__()
        self.excluded_ids = list(excluded_ids)

    def run(self) -> None:
        entries: List[Tuple[str, str]] = []
        for pid in self.excluded_ids:
            name = WingetClient.resolve_package_name(pid)
            entries.append((pid, name))
        self.result.emit(entries)
        self.finished.emit()


class WindowControlButton(QToolButton):
    """A circular window-control button painted entirely with QPainter.

    symbol        – one of 'min', 'max', 'close'
    color_normal  – idle circle fill (None = transparent until hover)
    color_hover   – circle fill on hover
    """

    def __init__(
        self,
        symbol: str,
        color_normal: Optional[str],
        color_hover: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._symbol = symbol
        self._color_normal = QColor(color_normal) if color_normal else None
        self._color_hover = QColor(color_hover)
        self._hovered = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("WindowControlButton")
        self.setIcon(QIcon())

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 4

        # Circle fill: subtle at idle, brighter on hover.
        if self._hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color_hover)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        elif self._color_normal:
            idle_fill = QColor(self._color_normal)
            idle_fill.setAlphaF(0.35)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(idle_fill)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Symbol is always drawn so each control is recognisable at idle.
        if self._hovered:
            symbol_color = QColor("#0B0C0F")
        elif self._symbol == "close":
            symbol_color = QColor("#FF9C96")
        else:
            symbol_color = QColor(TEXT)
        pen = QPen(symbol_color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = int(r * 0.42)
        x0, y0 = int(cx) - m, int(cy) - m
        x1, y1 = int(cx) + m, int(cy) + m
        if self._symbol == "close":
            painter.drawLine(x0, y0, x1, y1)
            painter.drawLine(x1, y0, x0, y1)
        elif self._symbol == "min":
            painter.drawLine(x0, int(cy), x1, int(cy))
        elif self._symbol in ("max", "restore"):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x0, y0, m * 2, m * 2)
        painter.end()


class SearchBar(QWidget):
    """A QLineEdit wrapped in a custom widget that paints a magnifier icon
    on the left and shows a clear (X) button when text is present.

    Connect signals via the exposed ``line_edit`` attribute.
    """

    def __init__(self, placeholder: str = "Search...", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBar")
        self.setFixedHeight(38)

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setObjectName("SearchInput")
        self.line_edit.setStyleSheet(
            "QLineEdit#SearchInput { background: transparent; border: none;"
            " color: #E7EAF0; padding: 0px; }"
        )

        self._clear_btn = QToolButton(self)
        self._clear_btn.setText("✕")
        self._clear_btn.setObjectName("SearchClearButton")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setFixedSize(20, 20)
        self._clear_btn.setVisible(False)
        self._clear_btn.clicked.connect(self.line_edit.clear)
        self.line_edit.textChanged.connect(
            lambda t: self._clear_btn.setVisible(bool(t))
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(38, 0, 8, 0)
        layout.setSpacing(4)
        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self._clear_btn)

        self._focused = False
        self.line_edit.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        from PyQt6.QtCore import QEvent

        if obj is self.line_edit:
            if event.type() == QEvent.Type.FocusIn:
                self._focused = True
                self.update()
            elif event.type() == QEvent.Type.FocusOut:
                self._focused = False
                self.update()
        return super().eventFilter(obj, event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = 10

        border_color = QColor(BORDER_FOCUS if self._focused else BORDER_SOFT)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QColor(SURFACE))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, radius, radius)

        icon_cx, icon_cy = 18, h // 2
        icon_r = 6
        pen = QPen(QColor(TEXT_MUTED))
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(icon_cx - icon_r, icon_cy - icon_r, icon_r * 2, icon_r * 2)
        off = int(icon_r * 0.707)
        painter.drawLine(
            icon_cx + off, icon_cy + off, icon_cx + off + 4, icon_cy + off + 4
        )
        painter.end()

    def text(self) -> str:
        return self.line_edit.text()


class VersionBadge(QWidget):
    """A rounded pill badge showing a version string.

    variant='installed'  -> muted grey pill
    variant='available'  -> cyan pill
    """

    def __init__(self, text: str, variant: str = "installed", parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._variant = variant
        self.setFont(QFont("Bahnschrift", 8))
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setFixedHeight(22)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QFontMetrics

        fm = QFontMetrics(self.font())
        width = fm.horizontalAdvance(self._text) + 22
        return QSize(max(width, 52), 22)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.height() / 2
        rect = self.rect().adjusted(0, 1, -1, -2)

        if self._variant == "available":
            bg = QColor(ACCENT)
            bg.setAlphaF(0.15)
            border = QColor(ACCENT)
            text_color = QColor(ACCENT_SOFT)
        else:
            bg = QColor(BORDER_MID)
            bg.setAlphaF(0.5)
            border = QColor(BORDER_SOFT)
            text_color = QColor(TEXT_MUTED)

        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class EmptyStateWidget(QWidget):
    """Shown in place of the table when there is nothing to display.

    States: 'idle' | 'scanning' | 'up_to_date'
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._angle = 0.0

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(16)
        self._spin_timer.timeout.connect(self._advance_spinner)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        self._icon_canvas = QWidget()
        self._icon_canvas.setFixedSize(72, 72)
        self._icon_canvas.paintEvent = self._paint_icon
        layout.addWidget(self._icon_canvas, 0, Qt.AlignmentFlag.AlignHCenter)

        self._title_lbl = QLabel("Scan to check for updates")
        self._title_lbl.setObjectName("EmptyStateTitle")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_lbl)

        self._sub_lbl = QLabel("Click 'Check for Updates' to begin")
        self._sub_lbl.setObjectName("EmptyStateSub")
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._sub_lbl)

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "idle":
            self._spin_timer.stop()
            self._title_lbl.setText("Scan to check for updates")
            self._sub_lbl.setText("Click 'Check for Updates' to begin")
        elif state == "scanning":
            self._angle = 0.0
            self._spin_timer.start()
            self._title_lbl.setText("Scanning for updates…")
            self._sub_lbl.setText("This may take a moment")
        elif state == "up_to_date":
            self._spin_timer.stop()
            self._title_lbl.setText("All software is up to date")
            self._sub_lbl.setText("No updates were found")
        self._icon_canvas.update()

    def _advance_spinner(self) -> None:
        self._angle = (self._angle + 4.0) % 360.0
        self._icon_canvas.update()

    def _paint_icon(self, event) -> None:
        w = self._icon_canvas.width()
        h = self._icon_canvas.height()
        painter = QPainter(self._icon_canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = w / 2, h / 2

        if self._state == "scanning":
            track_pen = QPen(QColor(BORDER_MID), 4)
            painter.setPen(track_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(int(cx - 28), int(cy - 28), 56, 56, 0, 360 * 16)
            pen = QPen(QColor(ACCENT), 4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                int(cx - 28), int(cy - 28), 56, 56, int(-self._angle * 16), 270 * 16
            )
        elif self._state == "up_to_date":
            pen = QPen(QColor(SUCCESS), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(cx - 28), int(cy - 28), 56, 56)
            path = QPainterPath()
            path.moveTo(cx - 12, cy)
            path.lineTo(cx - 4, cy + 10)
            path.lineTo(cx + 14, cy - 10)
            painter.drawPath(path)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            bg = QColor(BORDER_MID)
            bg.setAlphaF(0.4)
            painter.setBrush(bg)
            painter.drawRoundedRect(int(cx - 28), int(cy - 28), 56, 56, 14, 14)
            pen = QPen(QColor(TEXT_MUTED), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            arrow = QPainterPath()
            arrow.moveTo(cx, cy + 14)
            arrow.lineTo(cx, cy - 14)
            arrow.moveTo(cx, cy - 14)
            arrow.lineTo(cx + 10, cy - 4)
            arrow.moveTo(cx, cy - 14)
            arrow.lineTo(cx - 10, cy - 4)
            painter.drawPath(arrow)
        painter.end()


class StatusChip(QWidget):
    """Footer status indicator: a colored dot plus a text label.

    States map to dot colors; 'scanning' pulses via an opacity animation.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._dot_opacity = 1.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self._dot_canvas = QWidget()
        self._dot_canvas.setFixedSize(10, 10)
        self._dot_canvas.paintEvent = self._paint_dot
        layout.addWidget(self._dot_canvas, 0, Qt.AlignmentFlag.AlignVCenter)

        self._label = QLabel("Idle")
        self._label.setObjectName("FooterText")
        layout.addWidget(self._label)

        self._anim = QPropertyAnimation(self, b"dot_opacity")
        self._anim.setDuration(1000)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.2)
        self._anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        self._anim.setLoopCount(-1)

    @pyqtProperty(float)
    def dot_opacity(self) -> float:
        return self._dot_opacity

    @dot_opacity.setter
    def dot_opacity(self, value: float) -> None:
        self._dot_opacity = value
        self._dot_canvas.update()

    def set_state(self, state: str, text: str) -> None:
        self._state = state
        self._label.setText(text)
        if state == "scanning":
            self._anim.start()
        else:
            self._anim.stop()
            self._dot_opacity = 1.0
        self._dot_canvas.update()

    def _paint_dot(self, event) -> None:
        color_map = {
            "idle": TEXT_MUTED,
            "scanning": ACCENT,
            "updating": WARNING,
            "done": SUCCESS,
            "error": ERROR,
        }
        c = QColor(color_map.get(self._state, TEXT_MUTED))
        c.setAlphaF(self._dot_opacity)
        painter = QPainter(self._dot_canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(0, 0, 9, 9)
        painter.end()


class _FooterProxy:
    """Thin shim so legacy ``self.footer_status.setText(...)`` calls route to a
    StatusChip without changing any call site."""

    def __init__(self, chip: "StatusChip") -> None:
        self._chip = chip

    def setText(self, text: str) -> None:
        lowered = text.lower()
        if text == "Idle":
            state = "idle"
        elif "scan" in lowered:
            state = "scanning"
        elif "updating" in lowered:
            state = "updating"
        elif "updated" in lowered:
            state = "done"
        else:
            state = "idle"
        self._chip.set_state(state, text)


class TitleBar(QFrame):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(50)
        self._drag_pos: Optional[QPoint] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 5, 12, 5)
        layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setPixmap(build_logo_pixmap(26))
        logo_label.setFixedSize(28, 28)

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(2)
        title = QLabel(APP_TITLE)
        title.setObjectName("TitleText")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("SubtitleText")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)

        title_wrap = QHBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(10)
        title_wrap.addWidget(logo_label)
        title_wrap.addLayout(title_block)

        left = QWidget()
        left.setLayout(title_wrap)

        layout.addWidget(left)
        layout.addStretch(1)

        self.min_button = WindowControlButton(
            symbol="min", color_normal="#2A3040", color_hover="#5A6070"
        )
        self.max_button = WindowControlButton(
            symbol="max", color_normal="#2A3040", color_hover="#5A6070"
        )
        self.close_button = WindowControlButton(
            symbol="close", color_normal="#2A3040", color_hover="#E0443A"
        )

        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

        self.min_button.clicked.connect(parent.showMinimized)
        self.max_button.clicked.connect(parent.toggle_maximize)
        self.close_button.clicked.connect(parent.close)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        gradient = QLinearGradient(0, 0, w, 0)
        gradient.setColorAt(0.0, QColor(ACCENT))
        gradient.setColorAt(0.6, QColor(ACCENT))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        pen = QPen()
        pen.setBrush(gradient)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(0, h - 1, w, h - 1)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().toggle_maximize()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1100, 680)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.fake_updates_path = resolve_data_path("fake_updates.json")
        self.excluded_updates_path = resolve_data_path("excluded_updates.json")
        self.skipped_updates_path = resolve_data_path("skipped_updates.json")

        self.fake_updates: Dict[str, str] = load_json(self.fake_updates_path)
        self.excluded_updates: Dict[str, bool] = load_json(self.excluded_updates_path)
        self.skipped_updates: Dict[str, str] = load_json(self.skipped_updates_path)

        self.update_in_progress = False
        self.updates: List[UpdateItem] = []
        self.updates_by_id: Dict[str, UpdateItem] = {}
        self._current_thread: Optional[QThread] = None
        self.scan_in_progress = False
        self._scan_watchdog = QTimer(self)
        self._scan_watchdog.setSingleShot(True)
        self._scan_watchdog.timeout.connect(self._handle_scan_timeout)

        self._build_ui()
        self._setup_tray()
        self._show_empty_state("idle")

        QTimer.singleShot(300, self.check_for_updates)

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

        shell_layout.addWidget(header)

        header_divider = QFrame()
        header_divider.setObjectName("HeaderDivider")
        header_divider.setFrameShape(QFrame.Shape.HLine)
        header_divider.setFixedHeight(1)
        shell_layout.addWidget(header_divider)

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
        shell_layout.addWidget(search_row)

        self.stack = QStackedWidget()
        shell_layout.addWidget(self.stack, 1)

        self.updates_view = QWidget()
        updates_layout = QVBoxLayout(self.updates_view)
        updates_layout.setContentsMargins(0, 0, 0, 0)
        updates_layout.setSpacing(10)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Software",
                "Installed",
                "Available",
                "Size",
                "Update",
                "Exclude",
                "Skip",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        for action_col in (4, 5, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                action_col, QHeaderView.ResizeMode.Fixed
            )
            self.table.setColumnWidth(action_col, 92)
        self.table.itemSelectionChanged.connect(self.update_selected_state)
        updates_layout.addWidget(self.table)
        self.stack.addWidget(self.updates_view)

        self.empty_state = EmptyStateWidget()
        self.stack.addWidget(self.empty_state)

        self.exclusions_view = QWidget()
        exclusions_layout = QVBoxLayout(self.exclusions_view)
        exclusions_layout.setContentsMargins(0, 0, 0, 0)
        exclusions_layout.setSpacing(12)
        self.exclusions_hint = QLabel(
            "Excluded apps are hidden from the updates list. Click Unexclude to restore them."
        )
        self.exclusions_hint.setObjectName("HintText")
        exclusions_layout.addWidget(self.exclusions_hint)
        self.exclusions_table = QTableWidget(0, 2)
        self.exclusions_table.setHorizontalHeaderLabels(["Software", "Action"])
        self.exclusions_table.verticalHeader().setVisible(False)
        self.exclusions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.exclusions_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.exclusions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.exclusions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.exclusions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        exclusions_layout.addWidget(self.exclusions_table)
        self.stack.addWidget(self.exclusions_view)

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
        self.footer_status = _FooterProxy(self.footer_status_chip)
        self.size_grip = QSizeGrip(self)
        footer_layout.addWidget(self.size_grip)
        shell_layout.addWidget(footer)

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
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _make_button(self, text: str, primary: bool) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("PrimaryButton" if primary else "GhostButton")
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
        query = self.search_input.text().strip().lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            package_id = name_item.data(Qt.ItemDataRole.UserRole) if name_item else ""
            name = name_item.text().lower() if name_item else ""
            match = query in name or (package_id and query in package_id.lower())
            self.table.setRowHidden(row, not match)

    def update_selected_state(self) -> None:
        if self.update_in_progress:
            self.update_selected_button.setEnabled(False)
            return
        selected = bool(self.table.selectionModel().selectedRows())
        self.update_selected_button.setEnabled(selected and bool(self.updates))

    def toggle_exclusions_view(self) -> None:
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
        self.check_button.setEnabled(False)
        self.update_all_button.setEnabled(False)
        self.update_selected_button.setEnabled(False)
        self.manage_exclusions_button.setEnabled(False)

    def unlock_controls(self) -> None:
        self.check_button.setEnabled(True)
        self.manage_exclusions_button.setEnabled(True)
        self.update_all_button.setEnabled(bool(self.updates))
        self.update_selected_button.setEnabled(
            bool(self.updates) and bool(self.table.selectionModel().selectedRows())
        )

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
            self,
            "Error",
            f"winget timed out after {WINGET_TIMEOUT_SECONDS} seconds",
        )

    def check_for_updates(self) -> None:
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

        worker = ScanWorker(self.fake_updates, self.excluded_updates, self.skipped_updates)
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
        self, updates: List[UpdateItem], new_skipped: Dict[str, str], skipped_changed: bool
    ) -> None:
        self._finish_scan()
        self.updates = updates
        self.updates_by_id = {u.package_id: u for u in updates}
        if skipped_changed:
            try:
                save_json(self.skipped_updates_path, new_skipped)
                self.skipped_updates = new_skipped
            except Exception as exc:
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
            update_btn.setToolTip(f"Update {update.name} to {update.available_version}")
            update_btn.clicked.connect(lambda _, pid=update.package_id: self.update_single(pid))
            self.table.setCellWidget(row, 4, update_btn)

            exclude_btn = self._make_table_button("Exclude", "ActionExcludeButton")
            exclude_btn.setToolTip(f"Permanently exclude {update.name} from updates")
            exclude_btn.clicked.connect(lambda _, pid=update.package_id: self.exclude_package(pid))
            self.table.setCellWidget(row, 5, exclude_btn)

            skip_btn = self._make_table_button("Skip", "ActionSkipButton")
            skip_btn.setToolTip(f"Skip version {update.available_version} of {update.name}")
            skip_btn.clicked.connect(lambda _, pid=update.package_id: self.skip_version(pid))
            self.table.setCellWidget(row, 6, skip_btn)

            self.table.setRowHeight(row, 40)

        self.apply_filter()
        self.result_counter.setText(f"{len(self.updates)} updates")
        self.update_selected_state()
        self._update_badge()

    def _make_table_button(self, text: str, obj_name: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setObjectName(obj_name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setMinimumWidth(76)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return btn

    def update_single(self, package_id: str) -> None:
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
            self,
            "Confirm Update",
            f"Update {len(selected)} selected package(s)?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.start_update(selected, "Updating selected software...")

    def update_all(self) -> None:
        if self.update_in_progress:
            QMessageBox.warning(self, "Warning", "An update is already in progress")
            return
        if not self.updates:
            QMessageBox.information(self, "Info", "No updates available")
            return
        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"Update all {len(self.updates)} package(s)?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        package_ids = [u.package_id for u in self.updates]
        self.start_update(package_ids, "Updating all software...")

    def start_update(self, package_ids: List[str], status_text: str) -> None:
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
                except Exception as exc:
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
                QMessageBox.information(self, "Success", "All updates completed successfully")
            else:
                self.status_label.setText(f"Found {len(self.updates)} update(s)")
        else:
            self.status_label.setText("Update failed")
        self.unlock_controls()
        self.update_selected_state()
        self._update_badge()

    def remove_update(self, package_id: str) -> None:
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

    def exclude_package(self, package_id: str) -> None:
        if package_id in self.excluded_updates:
            return
        update = self.updates_by_id.get(package_id)
        if not update:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Exclusion",
            f"Exclude updates for {update.name} permanently?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.excluded_updates[package_id] = True
            save_json(self.excluded_updates_path, self.excluded_updates)
            self.remove_update(package_id)
            self.status_label.setText(f"Excluded {update.name} from updates")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error excluding package: {exc}")
        self.unlock_controls()

    def skip_version(self, package_id: str) -> None:
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
                f"Unable to skip {update.name} because no version information is available.",
            )
            return
        if self.skipped_updates.get(package_id) == available_version:
            self.remove_update(package_id)
            return
        reply = QMessageBox.question(
            self,
            "Skip This Version",
            (
                f"Skip version {available_version} of {update.name}?\n\n"
                "You will see this software again when a newer version is released."
            ),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.skipped_updates[package_id] = available_version
            save_json(self.skipped_updates_path, self.skipped_updates)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error saving skipped version: {exc}")
            return
        self.remove_update(package_id)
        self.status_label.setText(f"Skipped {update.name} (version {available_version})")
        self.unlock_controls()

    def load_exclusions(self) -> None:
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
            action_btn.clicked.connect(lambda _, pid=package_id: self.unexclude(pid))
            self.exclusions_table.setCellWidget(row, 1, action_btn)
            self.exclusions_table.setRowHeight(row, 44)
        if entries:
            self.status_label.setText(f"Manage Exclusions - {len(entries)} item(s)")
        else:
            self.status_label.setText("No excluded packages")

    def unexclude(self, package_id: str) -> None:
        if package_id in self.excluded_updates:
            try:
                self.excluded_updates.pop(package_id, None)
                save_json(self.excluded_updates_path, self.excluded_updates)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Error saving exclusions: {exc}")
                return
        self.load_exclusions()

    def closeEvent(self, event) -> None:
        if self.tray:
            self.tray.hide()
        event.accept()


def build_logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#21D4FD"))
    gradient.setColorAt(1, QColor("#2BD98A"))

    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, size * 0.35, size * 0.35)

    painter.setBrush(QColor("#0B0C0F"))
    inset = int(size * 0.28)
    painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)

    # Upward arrow inside the dark circle (represents "update").
    cx, cy = size / 2, size / 2
    arrow_h = size * 0.30
    arrow_w = size * 0.20
    path = QPainterPath()
    path.moveTo(cx, cy - arrow_h / 2)
    path.lineTo(cx + arrow_w / 2, cy)
    path.lineTo(cx + arrow_w * 0.25, cy)
    path.lineTo(cx + arrow_w * 0.25, cy + arrow_h / 2)
    path.lineTo(cx - arrow_w * 0.25, cy + arrow_h / 2)
    path.lineTo(cx - arrow_w * 0.25, cy)
    path.lineTo(cx - arrow_w / 2, cy)
    path.closeSubpath()

    arrow_gradient = QLinearGradient(0, 0, size, size)
    arrow_gradient.setColorAt(0, QColor("#21D4FD"))
    arrow_gradient.setColorAt(1, QColor("#2BD98A"))
    painter.setBrush(arrow_gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)

    painter.end()
    return pixmap


def apply_dark_theme(app: QApplication) -> None:
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(BG))
    palette.setColor(palette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(palette.ColorRole.Base, QColor("#0F1116"))
    palette.setColor(palette.ColorRole.AlternateBase, QColor("#12161C"))
    palette.setColor(palette.ColorRole.Text, QColor(TEXT))
    palette.setColor(palette.ColorRole.Button, QColor("#161A20"))
    palette.setColor(palette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(palette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(palette.ColorRole.HighlightedText, QColor("#0B0C0F"))
    app.setPalette(palette)

    font = QFont("Bahnschrift", 10)
    app.setFont(font)

    app.setStyleSheet(
        f"""
        /* -- Base -- */
        QMainWindow {{
            background: {BG};
        }}
        QFrame#Shell {{
            background: {PANEL};
            border: 1px solid {PANEL_BORDER};
            border-radius: 18px;
        }}

        /* -- Title Bar -- */
        QFrame#TitleBar {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {TITLE_BG_1}, stop:1 {TITLE_BG_2});
            border: 1px solid {PANEL_BORDER};
            border-radius: 16px;
        }}
        QLabel#TitleText {{
            font-size: 14pt;
            font-weight: 700;
            color: #EAF5FF;
        }}
        QLabel#SubtitleText {{
            font-size: 9pt;
            color: #94A2B8;
        }}
        QToolButton#WindowControlButton {{
            background: transparent;
            border: none;
            padding: 0px;
        }}

        /* -- Header / Section -- */
        QLabel#SectionTitle {{
            font-size: 14pt;
            font-weight: 700;
            color: #E9ECF2;
        }}
        QLabel#StatusText {{
            font-size: 10pt;
            color: {TEXT_MUTED};
        }}
        QLabel#HintText {{
            color: #96A0B4;
        }}
        QLabel#CounterText {{
            color: {ACCENT_SOFT};
            font-weight: 600;
        }}
        QLabel#UpdateBadge {{
            background: {ACCENT};
            color: {BG};
            font-size: 8pt;
            font-weight: 700;
            border-radius: 10px;
            padding: 2px 8px;
            min-width: 18px;
        }}
        QFrame#HeaderDivider {{
            background: {PANEL_BORDER};
            border: none;
        }}

        /* -- Search Bar -- */
        QWidget#SearchBar {{
            background: transparent;
        }}
        QToolButton#SearchClearButton {{
            background: transparent;
            border: none;
            color: {TEXT_MUTED};
            font-size: 10pt;
        }}
        QToolButton#SearchClearButton:hover {{
            color: {TEXT};
        }}

        /* -- Empty State -- */
        QLabel#EmptyStateTitle {{
            font-size: 13pt;
            font-weight: 600;
            color: {TEXT};
        }}
        QLabel#EmptyStateSub {{
            font-size: 9pt;
            color: {TEXT_MUTED};
        }}

        /* -- Buttons -- */
        QToolButton#PrimaryButton {{
            background: {ACCENT};
            color: {BG};
            border: none;
            border-radius: 10px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        QToolButton#PrimaryButton:hover {{
            background: {ACCENT_SOFT};
        }}
        QToolButton#PrimaryButton:disabled {{
            background: #2B3A44;
            color: #7C8A9A;
        }}
        QToolButton#GhostButton {{
            background: {BUTTON_BG};
            color: #E1E6EE;
            border: 1px solid #262B36;
            border-radius: 10px;
            padding: 8px 14px;
        }}
        QToolButton#GhostButton:hover {{
            border-color: {ACCENT};
            color: {ACCENT_SOFT};
        }}
        QToolButton#GhostButton:disabled {{
            color: #6F7A8A;
            border-color: #20242D;
        }}

        /* -- Table Action Buttons -- */
        QToolButton#ActionUpdateButton {{
            background: rgba(33, 212, 253, 0.12);
            color: {ACCENT_SOFT};
            border: 1px solid {ACCENT};
            border-radius: 7px;
            padding: 4px 10px;
            font-size: 8pt;
            font-weight: 600;
        }}
        QToolButton#ActionUpdateButton:hover {{
            background: rgba(33, 212, 253, 0.22);
        }}
        QToolButton#ActionExcludeButton {{
            background: transparent;
            color: {WARNING};
            border: 1px solid {WARN_BORDER};
            border-radius: 7px;
            padding: 4px 10px;
            font-size: 8pt;
        }}
        QToolButton#ActionExcludeButton:hover {{
            background: rgba(240, 200, 75, 0.10);
        }}
        QToolButton#ActionSkipButton {{
            background: transparent;
            color: {TEXT_MUTED};
            border: 1px solid {MUTED_BORDER};
            border-radius: 7px;
            padding: 4px 10px;
            font-size: 8pt;
        }}
        QToolButton#ActionSkipButton:hover {{
            color: {TEXT};
            border-color: #3A4758;
        }}
        QToolButton#ActionButton {{
            background: {BUTTON_BG};
            color: #E1E6EE;
            border: 1px solid {MUTED_BORDER};
            border-radius: 8px;
            padding: 5px 10px;
            font-size: 8pt;
        }}
        QToolButton#ActionButton:hover {{
            border-color: {ACCENT};
            color: {ACCENT_SOFT};
        }}

        /* -- Inputs -- */
        QLineEdit {{
            background: {SURFACE};
            border: 1px solid {BORDER_SOFT};
            border-radius: 10px;
            padding: 8px 12px;
            color: {TEXT};
        }}
        QLineEdit:focus {{
            border-color: {ACCENT};
        }}

        /* -- Table -- */
        QTableWidget {{
            background: {SURFACE};
            border: 1px solid #1E2330;
            border-radius: 12px;
            gridline-color: #1A1E28;
            color: #E6E9F0;
            selection-background-color: #1E2B38;
            selection-color: #EAF5FF;
        }}
        QTableWidget::item {{
            padding: 4px 8px;
        }}
        QTableWidget::item:hover {{
            background: {HOVER};
        }}
        QTableWidget::item:selected {{
            background: #1E2B38;
        }}
        QHeaderView::section {{
            background: #141821;
            color: #B7C1D1;
            padding: 8px;
            border: none;
            font-weight: 600;
        }}
        QTableCornerButton::section {{
            background: #141821;
            border: none;
        }}

        /* -- Scrollbars -- */
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER_MID};
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #3A4560;
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {BORDER_MID};
            border-radius: 3px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #3A4560;
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}

        /* -- Progress Bar -- */
        QProgressBar {{
            background: {SURFACE};
            border: 1px solid {BORDER_SOFT};
            border-radius: 5px;
            height: 6px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT}, stop:1 {SUCCESS});
            border-radius: 5px;
        }}

        /* -- Footer -- */
        QLabel#FooterText {{
            color: #98A3B6;
            font-size: 9pt;
        }}

        /* -- Message Box -- */
        QMessageBox {{
            background: {PANEL};
            color: {TEXT};
        }}
        QMessageBox QLabel {{
            color: {TEXT};
            font-size: 10pt;
        }}
        QMessageBox QPushButton {{
            background: {BUTTON_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 8px;
            padding: 6px 18px;
            min-width: 80px;
        }}
        QMessageBox QPushButton:hover {{
            border-color: {ACCENT};
            color: {ACCENT_SOFT};
        }}
        QMessageBox QPushButton:default {{
            background: {ACCENT};
            color: {BG};
            border: none;
            font-weight: 600;
        }}

        /* -- Tooltips -- */
        QToolTip {{
            background: #1A1F2B;
            color: {TEXT};
            border: 1px solid {ACCENT};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 9pt;
        }}

        /* -- Context Menu -- */
        QMenu {{
            background: {PANEL};
            color: {TEXT};
            border: 1px solid #262B36;
            border-radius: 8px;
        }}
        QMenu::item {{
            padding: 6px 22px;
        }}
        QMenu::item:selected {{
            background: #1A202B;
            color: {ACCENT_SOFT};
        }}
        QMenu::separator {{
            height: 1px;
            background: {PANEL_BORDER};
            margin: 4px 10px;
        }}
        """
    )


def main() -> None:
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
