"""
Improved Windows software updater GUI.

This module contains a Tkinter application that wraps the Windows Package
Manager (winget) to scan for application updates and apply them.  It
improves upon the original implementation by providing a more modern and
flexible user interface, support for batch updating only a subset of the
available packages, and the ability to permanently exclude specific
packages from future scans.

The application is still designed to run on Windows with winget installed.
When run, the user is automatically presented with a list of available
updates.  Each row of the list includes controls for updating or
excluding the corresponding package.  Multiple rows can be selected
(using Ctrl‑click or Shift‑click) and updated together via a dedicated
"Update Selected" button.  Exclusions are persisted to disk and
respected on subsequent scans.

The update logic itself has not changed: packages are updated via
``winget upgrade <package id> --accept-source-agreements`` and the
progress bar reflects the number of operations being performed.  When a
package is excluded, its identifier is recorded in an ``excluded_updates.json``
file alongside any fake updates discovered at runtime.

Note that this script depends on ``plyer`` for notifications and
``requests`` for determining download sizes.  On non‑Windows platforms
the functionality is limited; however, the GUI remains responsive thanks
to threading and careful use of ``after`` callbacks.
"""

import json
import os
import re
import subprocess
import sys
import threading
from typing import Dict, List, Optional

import requests
import tkinter as tk
from plyer import notification
from tkinter import ttk, messagebox

try:
    # Use win10toast_click for Windows toast notifications if available
    from win10toast_click import ToastNotifier as WinToastNotifier  # type: ignore
except Exception:
    WinToastNotifier = None


class SoftwareUpdater:
    """A Tkinter GUI for updating Windows software via winget.

    This class encapsulates all of the application state and behaviour,
    including UI construction, background scanning for updates, applying
    updates, and persisting fake/excluded update metadata.
    """

    #: JSON file used to record fake updates (where winget reports an
    #: available version for a package that cannot actually be updated).
    FAKE_UPDATES_FILE = "fake_updates.json"
    #: JSON file used to record permanently excluded packages.  Excluded
    #: packages will not show up in the update list on subsequent scans.
    EXCLUDED_UPDATES_FILE = "excluded_updates.json"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Windows Software Updater")
        # Fix the window size but allow resizing downwards if the user
        # collapses the tree.  A minimum width of 1000px provides room
        # for the extra columns that were added for selection/exclusion.
        self.root.geometry("1200x600")

        # Header bar with app title, subtitle, and primary actions
        header_bg = "#0d6efd"
        header_fg = "#ffffff"
        sub_fg = "#eaf2ff"
        self.header = tk.Frame(root, bg=header_bg)
        self.header.pack(fill=tk.X)

        icon_canvas = tk.Canvas(self.header, width=28, height=28, bg=header_bg, highlightthickness=0)
        icon_canvas.grid(row=0, column=0, padx=(12, 8), pady=10)
        icon_canvas.create_oval(2, 2, 26, 26, fill="#ffffff", outline="")
        icon_canvas.create_rectangle(8, 9, 20, 12, fill=header_bg, outline="")
        icon_canvas.create_rectangle(8, 14, 20, 17, fill=header_bg, outline="")

        title_block = tk.Frame(self.header, bg=header_bg)
        title_block.grid(row=0, column=1, sticky="w")
        tk.Label(
            title_block,
            text="Windows Software Updater",
            font=("Segoe UI", 16, "bold"),
            fg=header_fg,
            bg=header_bg,
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="Powered by Windows Package Manager (winget)",
            font=("Segoe UI", 10),
            fg=sub_fg,
            bg=header_bg,
        ).pack(anchor="w")

        self.toolbar = ttk.Frame(self.header)
        self.toolbar.grid(row=0, column=2, sticky="e", padx=12)
        self.header.grid_columnconfigure(1, weight=1)

        self.check_button = ttk.Button(
            self.toolbar,
            text="Check for Updates",
            command=self.check_for_updates,
        )
        self.check_button.pack(side=tk.LEFT, padx=(0, 8))

        self.update_all_button = ttk.Button(
            self.toolbar,
            text="Update All",
            state=tk.DISABLED,
            command=self.update_all,
        )
        self.update_all_button.pack(side=tk.LEFT, padx=(0, 8))

        self.update_selected_button = ttk.Button(
            self.toolbar,
            text="Update Selected",
            state=tk.DISABLED,
            command=self.update_selected,
        )
        self.update_selected_button.pack(side=tk.LEFT)

        ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Configure styles for a more modern look and feel.  Increase
        # row height in the treeview for better readability and adjust
        # fonts globally via ttk.Style.  Note that ttk widgets share
        # style names; adjusting the treeview will not affect labels.
        self.style = ttk.Style()
        try:
            if "vista" in self.style.theme_names():
                self.style.theme_use("vista")
            else:
                self.style.theme_use("clam")
        except Exception:
            self.style.theme_use("default")
        self.style.configure(
            "TButton", padding=6, relief="flat", font=("Helvetica", 10)
        )
        self.style.configure(
            "Title.TLabel", font=("Helvetica", 16, "bold")
        )
        self.style.configure(
            "Subtitle.TLabel", font=("Helvetica", 12)
        )
        # Make tree headings bold and slightly larger
        self.style.configure(
            "Treeview.Heading", font=("Helvetica", 10, "bold"), anchor="center"
        )
        # Increase the default row height of the treeview for spacing
        self.style.configure(
            "Treeview", font=("Helvetica", 10), rowheight=24
        )
        self.style.configure(
            "Dialog.TLabel", font=("Helvetica", 12, "bold"), foreground="red"
        )

        # Create the main frame.  All widgets except the top‑level title
        # are children of this frame, which simplifies layout.
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header moved to top bar; legacy title/buttons removed

        # Status label to communicate the current state to the user
        self.status_label = ttk.Label(
            self.main_frame,
            text="Click 'Check for Updates' to begin",
            style="Subtitle.TLabel",
        )
        self.status_label.grid(row=0, column=0, columnspan=3, pady=5, sticky=tk.W)

        # Progress bar.  We leave it empty until a scan or update begins.
        self.progress = ttk.Progressbar(
            self.main_frame,
            orient=tk.HORIZONTAL,
            length=100,
            mode="determinate",
        )
        self.progress.grid(row=1, column=0, columnspan=3, pady=10, sticky=tk.EW)
        # Stretch progress bar across the available width
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(2, weight=1)

        # Frame for the treeview and its scrollbar.  Making this a
        # separate frame allows the scrollbar to sit flush to the
        # right-hand side of the table.
        self.tree_frame = ttk.Frame(self.main_frame)
        self.tree_frame.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # Create the vertical scrollbar
        self.tree_scroll = ttk.Scrollbar(self.tree_frame)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Create the treeview itself.  It now includes an extra
        # "exclude" column for permanently hiding certain software.
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=(
                "name",
                "current_version",
                "new_version",
                "file_size",
                "update",
                "exclude",
            ),
            show="headings",
            yscrollcommand=self.tree_scroll.set,
            selectmode="extended",
        )
        self.tree.heading("name", text="Software Name")
        self.tree.heading("current_version", text="Current Version")
        self.tree.heading("new_version", text="Available Version")
        self.tree.heading("file_size", text="New Version Size")
        self.tree.heading("update", text="Action")
        self.tree.heading("exclude", text="Exclude")
        # Column widths tuned to fit the new table.  The exclude
        # column is narrow as it only contains a link.
        self.tree.column("name", width=350, anchor="w")
        self.tree.column("current_version", width=150, anchor="center")
        self.tree.column("new_version", width=150, anchor="center")
        self.tree.column("file_size", width=120, anchor="center")
        self.tree.column("update", width=100, anchor="center")
        self.tree.column("exclude", width=100, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll.config(command=self.tree.yview)

        # Bind a click handler on the treeview so we can interpret
        # clicks on the update and exclude columns.  Selecting rows for
        # batch updates is handled automatically by the ttk.Treeview.
        self.tree.bind("<Button-1>", self._handle_tree_click)

        # Track when the tree selection changes so we can enable or
        # disable the 'Update Selected' button.  Without this the
        # button would remain enabled after all rows have been removed.
        self.tree.bind("<<TreeviewSelect>>", self._handle_selection_change)

        # Initialize state.  'updates' holds the list of dictionaries
        # describing available updates.  'update_in_progress' is used
        # to prevent simultaneous update operations.  The fake and
        # excluded updates are persisted across runs.
        self.updates: List[Dict[str, Optional[str]]] = []
        self.update_in_progress = False
        self.fake_updates: Dict[str, str] = self._load_json(self.FAKE_UPDATES_FILE)
        self.excluded_updates: Dict[str, bool] = self._load_json(
            self.EXCLUDED_UPDATES_FILE
        )

        # Load icon path (packaged with PyInstaller if necessary)
        self.base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.icon_path = os.path.join(self.base_path, "icon.ico")

        # Create a toast notifier for update completion if win10toast_click is available.
        # This will be used to show a notification whenever a package finishes
        # updating successfully. If the import failed (e.g., on non-Windows
        # platforms or when the module is missing) this attribute will be None
        # and completion notifications will be suppressed gracefully.
        self.completion_notifier = None
        if WinToastNotifier is not None:
            try:
                self.completion_notifier = WinToastNotifier()
            except Exception:
                self.completion_notifier = None

        # Automatically check for updates when the application starts
        # to improve UX.
        self.check_for_updates()

    # ------------------------------------------------------------------
    # Persistent storage helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _load_json(filename: str) -> Dict:
        """Load a JSON file from disk and return an empty dict on error.

        All persistent metadata files (fake updates and excluded updates)
        share the same loading semantics.  When the file cannot be
        parsed or does not exist, an empty dict is returned.
        """
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    @staticmethod
    def _save_json(filename: str, data: Dict) -> None:
        """Persist a dictionary to disk as JSON, handling IO errors.

        In the unlikely event of an error during save, the user is
        presented with a message box in the caller.
        """
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            raise IOError(f"Error saving JSON file '{filename}': {e}")

    # ------------------------------------------------------------------
    # Notification helper
    # ------------------------------------------------------------------
    def show_notification(self, updatable_count: int) -> None:
        """Display a desktop notification about pending updates.

        Uses ``plyer`` to show a simple toast alert indicating how
        many packages can be updated.  On platforms where plyer
        notifications are not supported this function will quietly do
        nothing.
        """
        try:
            notification.notify(
                title="New Version Available!",
                message=f"{updatable_count} Update{'s' if updatable_count != 1 else ''} Available",
                app_name="Software Updater",
                timeout=5,
            )
        except Exception:
            # plyer may throw on unsupported platforms; ignore silently
            pass

    # ------------------------------------------------------------------
    # UI event handlers
    # ------------------------------------------------------------------
    def check_for_updates(self) -> None:
        """Kick off a background scan for available updates via winget.

        Disables the main control buttons while scanning, clears the
        existing table, and starts the progress bar.  The actual work
        happens in a separate thread to keep the GUI responsive.
        """
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return

        # Disable user interaction while scanning
        self.check_button.config(state=tk.DISABLED)
        self.update_all_button.config(state=tk.DISABLED)
        self.update_selected_button.config(state=tk.DISABLED)
        self.status_label.config(text="Checking for updates...")
        self.progress.config(mode="indeterminate")
        self.progress.start()

        # Clear previous results from the treeview and internal list
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.updates.clear()

        # Start scan in a background thread
        threading.Thread(target=self._check_for_updates_thread, daemon=True).start()

    def _check_for_updates_thread(self) -> None:
        """Worker thread for scanning available updates via winget.

        This method calls ``winget upgrade --accept-source-agreements`` and
        parses its output to build the list of available updates.  It
        filters out packages present in the ``fake_updates`` and
        ``excluded_updates`` dictionaries.  File sizes and executable
        paths are resolved before populating the UI on the main thread.
        """

        def run_command_silently(command: List[str]) -> subprocess.CompletedProcess:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                command,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        def get_file_size(package_id: str) -> Optional[float]:
            """Resolve the installer size in megabytes for a given package."""
            try:
                result = run_command_silently(["winget", "show", package_id])
                match = re.search(
                    r"Installer Url:\s*(https?://[^\s]+\.exe)",
                    result.stdout,
                    re.IGNORECASE,
                )
                if match:
                    link = match.group(1)
                    try:
                        response = requests.head(link, allow_redirects=True, timeout=10)
                        if "Content-Length" not in response.headers:
                            response = requests.get(link, stream=True, timeout=10)
                        size_bytes = int(response.headers.get("Content-Length", 0))
                        if size_bytes <= 0:
                            return None
                        size_mb = round(size_bytes / (1024 * 1024), 2)
                        return size_mb
                    except Exception:
                        return None
            except Exception:
                return None
            return None

        def get_executable_path(package_id: str, package_name: str) -> Optional[str]:
            """Attempt to find the installed executable for a package."""
            try:
                result = run_command_silently(["winget", "show", "--id", package_id, "--exact"])
                output = result.stdout
                match = re.search(
                    r"Install Location:\s*(.*?)\n",
                    output,
                    re.IGNORECASE,
                )
                if match:
                    install_path = match.group(1).strip()
                    if install_path and os.path.exists(install_path):
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

        try:
            result = run_command_silently(["winget", "upgrade", "--accept-source-agreements"])
            lines = result.stdout.split("\n")
            start_index = 0
            for i, line in enumerate(lines):
                if line.startswith("Name") and "Id" in line:
                    start_index = i + 1
                    break
            lines = lines[start_index:]
            temp_updates: List[Dict[str, Optional[str]]] = []
            for line in lines:
                if line.strip() and not line.startswith("-"):
                    line = line.replace("winget", "")
                    pattern = r"^(.*?)\s+([^\s]+)\s+([^\s]+\s*(?:\([^)]+\))?)\s+([^\s]+\s*(?:\([^)]+\))?)$"
                    match = re.match(pattern, line.strip())
                    parts: List[str] = []
                    if match:
                        parts = [
                            match.group(1).strip(),
                            match.group(2).strip(),
                            match.group(3).strip(),
                            match.group(4).strip(),
                        ]
                    if len(parts) >= 4:
                        package_name, package_id, installed_version, available_version = parts
                        if (
                            package_id in self.fake_updates
                            and self.fake_updates[package_id] == available_version
                        ) or (
                            package_id in self.excluded_updates
                        ):
                            continue
                        file_size = get_file_size(package_id)
                        executable_path = get_executable_path(package_id, package_name)
                        temp_updates.append(
                            {
                                "name": package_name,
                                "id": package_id,
                                "installed_version": installed_version,
                                "available_version": available_version,
                                "file_size": file_size,
                                "executable_path": executable_path,
                            }
                        )
            self.root.after(0, self._display_updates, temp_updates)
        except subprocess.CalledProcessError as e:
            self.root.after(
                0,
                self._show_error,
                f"Error checking for updates: {e.stderr}",
            )
        except FileNotFoundError:
            self.root.after(
                0,
                self._show_error,
                "winget not found. Please install Windows Package Manager.",
            )
        finally:
            self.root.after(0, self._stop_progress)

    def _display_updates(self, updates: List[Dict[str, Optional[str]]]) -> None:
        """Populate the treeview with a list of update dictionaries."""
        self.updates = updates
        for update in updates:
            package_id = update["id"]
            file_size_str = (
                f"{update['file_size']} MB" if update["file_size"] is not None else "N/A"
            )
            self.tree.insert(
                "",
                tk.END,
                iid=package_id,
                values=(
                    update["name"],
                    update["installed_version"],
                    update["available_version"],
                    file_size_str,
                    "Update",
                    "Exclude",
                ),
            )
        if updates:
            self.status_label.config(
                text=f"Found {len(updates)} available update{'s' if len(updates) != 1 else ''}"
            )
            self.update_all_button.config(state=tk.NORMAL)
            self.update_selected_button.config(state=tk.NORMAL)
            self.show_notification(len(updates))
        else:
            self.status_label.config(text="No updates available")
            self.update_all_button.config(state=tk.DISABLED)
            self.update_selected_button.config(state=tk.DISABLED)
        self.check_button.config(state=tk.NORMAL)

    def _handle_tree_click(self, event: tk.Event) -> None:
        """Respond to clicks on the treeview to handle inline actions."""
        if self.update_in_progress:
            return
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item:
            return
        if column == "#5":
            package_id = item
            self._update_single_by_id(package_id)
        elif column == "#6":
            package_id = item
            self._exclude_package_by_id(package_id)

    def _handle_selection_change(self, event: tk.Event) -> None:
        """Enable or disable the 'Update Selected' button based on selection."""
        if self.update_in_progress:
            return
        selected = bool(self.tree.selection())
        if selected and self.updates:
            self.update_selected_button.config(state=tk.NORMAL)
        else:
            self.update_selected_button.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Update actions
    # ------------------------------------------------------------------
    def _update_single_by_id(self, package_id: str) -> None:
        """Prompt the user and update a single package identified by id."""
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return
        update = next((u for u in self.updates if u["id"] == package_id), None)
        if not update:
            return
        package_name = update["name"]
        if not messagebox.askyesno(
            "Confirm Update",
            f"Update {package_name} to version {update['available_version']}?",
        ):
            return
        self.update_in_progress = True
        self.status_label.config(text=f"Updating {package_name}...")
        self.progress.config(mode="indeterminate")
        self.progress.start()
        self.check_button.config(state=tk.DISABLED)
        self.update_all_button.config(state=tk.DISABLED)
        self.update_selected_button.config(state=tk.DISABLED)
        threading.Thread(
            target=self._update_thread, args=([package_id],), daemon=True
        ).start()

    def update_selected(self) -> None:
        """Update only the packages currently selected in the treeview."""
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "No software selected for update")
            return
        package_ids: List[str] = list(selected_items)
        package_names = [
            next(
                (update["name"] for update in self.updates if update["id"] == pid),
                pid,
            )
            for pid in package_ids
        ]
        if not messagebox.askyesno(
            "Confirm Update",
            f"Update {len(package_ids)} selected package{'s' if len(package_ids) != 1 else ''}?\n\n"
            + "\n".join(package_names),
        ):
            return
        self.update_in_progress = True
        self.status_label.config(text="Updating selected software...")
        self.progress.config(mode="determinate", maximum=len(package_ids))
        self.progress["value"] = 0
        self.check_button.config(state=tk.DISABLED)
        self.update_all_button.config(state=tk.DISABLED)
        self.update_selected_button.config(state=tk.DISABLED)
        threading.Thread(
            target=self._update_thread,
            args=(package_ids,),
            daemon=True,
        ).start()

    def update_all(self) -> None:
        """Update all packages currently displayed in the treeview."""
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return
        if not self.updates:
            messagebox.showinfo("Info", "No updates available")
            return
        package_ids = [update["id"] for update in self.updates]
        package_names = [update["name"] for update in self.updates]
        if not messagebox.askyesno(
            "Confirm Update",
            f"Update all {len(package_ids)} package{'s' if len(package_ids) != 1 else ''}?\n\n"
            + "\n".join(package_names),
        ):
            return
        self.update_in_progress = True
        self.status_label.config(text="Updating all software...")
        self.progress.config(mode="determinate", maximum=len(package_ids))
        self.progress["value"] = 0
        self.check_button.config(state=tk.DISABLED)
        self.update_all_button.config(state=tk.DISABLED)
        self.update_selected_button.config(state=tk.DISABLED)
        threading.Thread(
            target=self._update_thread,
            args=(package_ids,),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Exclusion handling
    # ------------------------------------------------------------------
    def _exclude_package_by_id(self, package_id: str) -> None:
        """Permanently exclude a package from future scans."""
        if package_id in self.excluded_updates:
            return
        update = next((u for u in self.updates if u["id"] == package_id), None)
        if not update:
            return
        package_name = update["name"]
        if not messagebox.askyesno(
            "Confirm Exclusion",
            f"Exclude updates for {package_name} permanently?",
        ):
            return
        try:
            self.excluded_updates[package_id] = True
            self._save_json(self.EXCLUDED_UPDATES_FILE, self.excluded_updates)
            self._remove_package_by_id(package_id)
            self.status_label.config(text=f"Excluded {package_name} from updates")
            if self.updates:
                self.update_all_button.config(state=tk.NORMAL)
                self.update_selected_button.config(
                    state=tk.NORMAL if self.tree.selection() else tk.DISABLED
                )
            else:
                self.update_all_button.config(state=tk.DISABLED)
                self.update_selected_button.config(state=tk.DISABLED)
        except Exception as e:
            self._show_error(f"Error excluding package: {e}")

    def _remove_package_by_id(self, package_id: str) -> None:
        """Remove a package from the treeview and internal list by id."""
        try:
            self.tree.delete(package_id)
        except Exception:
            pass
        self.updates = [u for u in self.updates if u["id"] != package_id]
        if not self.updates:
            self.update_all_button.config(state=tk.DISABLED)
            self.update_selected_button.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Worker thread for performing updates
    # ------------------------------------------------------------------
    def _update_thread(self, package_ids: List[str]) -> None:
        """Background worker that iterates over a list of package ids.

        Each package is updated by executing ``winget upgrade <id>``.  The
        result of the command is parsed for success.  On successful
        completion the package is removed from the UI; if the update
        fails due to a fake update ("no package found" or "not
        installed") then the package is recorded in the fake updates
        file.  Any other error will trigger the error dialog and abort
        the batch.
        """
        def run_command_silently(command: List[str]) -> subprocess.CompletedProcess:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                command,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        success = True
        error_message = ""
        for i, package_id in enumerate(package_ids):
            command = ["winget", "upgrade", package_id, "--accept-source-agreements"]
            result = run_command_silently(command)
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            combined_output = (stdout + " " + stderr).lower()
            if result.returncode == 0 or "successfully upgraded" in combined_output:
                self.root.after(0, self._remove_package_by_id, package_id)
                self.root.after(0, lambda v=i + 1: self.progress.config(value=v))
                # Send a completion toast notification for this package
                try:
                    update_obj = next((u for u in self.updates if u["id"] == package_id), None)
                    pkg_name = update_obj["name"] if update_obj else package_id
                    if self.completion_notifier:
                        self.completion_notifier.show_toast(
                            f"{pkg_name} Updated",
                            f"{pkg_name} has been successfully updated.",
                            icon_path=self.icon_path,
                            duration=5,
                            threaded=True,
                        )
                except Exception:
                    pass
            else:
                if "no package found" in combined_output or "not installed" in combined_output:
                    self.root.after(0, self._handle_fake_update_by_id, package_id)
                else:
                    success = False
                    error_message = stderr or stdout or "Unknown error occurred"
                    self.root.after(
                        0,
                        self._update_complete,
                        False,
                        f"Error updating {package_id}",
                        package_id,
                    )
                    return
        if success:
            self.root.after(0, self._update_complete, True, "All updates completed successfully")

    def _handle_fake_update_by_id(self, package_id: str) -> None:
        """Record a fake update and remove it from the list."""
        update = next((u for u in self.updates if u["id"] == package_id), None)
        if not update:
            return
        package_name = update["name"]
        package_version = update["available_version"]
        self.fake_updates[package_id] = package_version
        try:
            self._save_json(self.FAKE_UPDATES_FILE, self.fake_updates)
        except Exception as e:
            self._show_error(str(e))
        self._remove_package_by_id(package_id)
        self.status_label.config(text=f"Removed fake update for {package_name}")

    # ------------------------------------------------------------------
    # Completion and error handling
    # ------------------------------------------------------------------
    def _update_complete(self, success: bool, message: str, package_id: Optional[str] = None) -> None:
        """Finalize UI state after an update operation."""
        self.update_in_progress = False
        self._stop_progress()
        if success:
            self.status_label.config(text=message)
            if not self.updates:
                messagebox.showinfo("Success", message)
        else:
            self.status_label.config(text="Update failed")
            dialog = tk.Toplevel(self.root)
            dialog.title("Update Error")
            dialog.geometry("300x130")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)
            screen_width = dialog.winfo_screenwidth()
            screen_height = dialog.winfo_screenheight()
            x = (screen_width - 300) // 2
            y = (screen_height - 130) // 2
            dialog.geometry(f"300x130+{x}+{y}")
            try:
                dialog.iconbitmap(self.icon_path)
            except Exception:
                pass
            dialog_frame = ttk.Frame(dialog, padding="10")
            dialog_frame.pack(fill=tk.BOTH, expand=True)
            ttk.Label(
                dialog_frame,
                text=message,
                style="Dialog.TLabel",
                justify=tk.CENTER,
                wraplength=350,
            ).pack(pady=(10, 15))
            button_frame = ttk.Frame(dialog_frame)
            button_frame.pack(pady=10)
            ttk.Button(
                button_frame,
                text="Close",
                command=dialog.destroy,
                width=12,
            ).pack(side=tk.LEFT, padx=10)
        self.check_button.config(state=tk.NORMAL)
        if self.updates:
            self.update_all_button.config(state=tk.NORMAL)
            self.update_selected_button.config(
                state=tk.NORMAL if self.tree.selection() else tk.DISABLED
            )
        else:
            self.update_all_button.config(state=tk.DISABLED)
            self.update_selected_button.config(state=tk.DISABLED)

    def _stop_progress(self) -> None:
        """Stop and reset the progress bar."""
        try:
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        """Display an error message and reset the UI state."""
        self._stop_progress()
        self.status_label.config(text="Error occurred")
        messagebox.showerror("Error", message)
        self.check_button.config(state=tk.NORMAL)
        self.update_all_button.config(state=tk.DISABLED)
        self.update_selected_button.config(state=tk.DISABLED)


def main() -> None:
    """Run the software updater as a standalone application."""
    root = tk.Tk()
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_path, "icon.ico")
        root.iconbitmap(icon_path)
    except Exception:
        pass
    app = SoftwareUpdater(root)
    root.mainloop()


if __name__ == "__main__":
    main()
