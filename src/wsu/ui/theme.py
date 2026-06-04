"""Centralised colour tokens and the global Qt stylesheet.

Keeping every colour and the full QSS in one module means the visual identity
can be retuned without hunting through widget code.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication

# -- Core palette -----------------------------------------------------------

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

# -- Extended surface & interaction tokens ----------------------------------

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


def build_stylesheet() -> str:
    """Return the application-wide Qt stylesheet."""
    return f"""
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


def apply_dark_theme(app: QApplication) -> None:
    """Apply the palette, default font, and stylesheet to ``app``."""
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(BG))
    palette.setColor(palette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(palette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(SURFACE_2))
    palette.setColor(palette.ColorRole.Text, QColor(TEXT))
    palette.setColor(palette.ColorRole.Button, QColor(BUTTON_BG))
    palette.setColor(palette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(palette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(palette.ColorRole.HighlightedText, QColor(BG))
    app.setPalette(palette)

    app.setFont(QFont("Bahnschrift", 10))
    app.setStyleSheet(build_stylesheet())
