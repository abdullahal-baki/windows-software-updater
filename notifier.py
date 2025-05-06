import subprocess
import re
import sys
import json
import os
from win10toast_click import ToastNotifier


class UpdateNotifier:
    def __init__(self):
        # Initialize variables
        self.updates = []
        self.fake_updates_file = r"C:\Users\Alamin\OneDrive\github\windows-software-updater\dist\fake_updates.json"
        self.fake_updates = self._load_fake_updates()
        
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        self.icon_path = os.path.join(base_path, 'icon.ico')
        self.toaster = ToastNotifier()
        self.updater_path = r"C:\Users\Alamin\OneDrive\github\windows-software-updater\dist\Updater.exe"
        
        # Check for updates on startup
        self.check_for_updates()

    def _load_fake_updates(self):
        """Load fake updates from the JSON file"""
        if os.path.exists(self.fake_updates_file):
            try:
                with open(self.fake_updates_file, 'r') as f:
                    data = json.load(f)
                    return data
            except (json.JSONDecodeError, IOError) as e:
                return {}
        return {}

    def _launch_updater(self):
        """Launch the Updater.exe application"""
        if os.path.exists(self.updater_path):
            os.startfile(self.updater_path)

    def show_notification(self, updatable_app):
        plural = "s" if updatable_app != 1 else ""
        self.toaster.show_toast(
            f"{updatable_app} Software Update{plural} Available!",
            "Open Software Updater app to install new versions.",
            icon_path=self.icon_path,
            duration=5,
            threaded=True,
            callback_on_click=self._launch_updater
        )

    def check_for_updates(self):
        def run_command_silently(command):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # prevent console window

            return subprocess.run(
                command,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        """Check for available updates"""
        try:
            result = run_command_silently(['winget', 'upgrade', '--accept-source-agreements'])
            
            # Parse the output (skip header lines and footer)
            lines = result.stdout.split('\n')
            start_index = 0
            for i, line in enumerate(lines):
                if line.startswith('Name') and 'Id' in line:
                    start_index = i + 1
                    break
            lines = lines[start_index:]
            self.updates = []
            
            total_lines = -1
            for line in lines:
                if line.strip() and not line.startswith('-'):
                    total_lines += 1
                    line = line.replace('winget', '')
                    print(line)
                    pattern = r"^(.*?)\s+([^\s]+)\s+([^\s]+\s*(?:\([^\)]+\))?)\s+([^\s]+\s*(?:\([^\)]+\))?)$"

                    match = re.match(pattern, line.strip())
                    if match:
                        parts = [
                            match.group(1).strip(),
                            match.group(2).strip(),
                            match.group(3).strip(),
                            match.group(4).strip()
                        ]
                    else:
                        parts = []                                            
                    if len(parts) >= 4:
                        available_version = parts[3]
                        
                        if parts[1] in self.fake_updates.keys() and self.fake_updates[parts[1]] == available_version:
                            total_lines -= 1
                        
                        else:
                            self.updates.append({
                                'name': parts[0],
                                'id': parts[1],
                                'installed_version': parts[2],
                                'available_version': available_version
                                })
            print(len(self.updates))
            if total_lines:
                self.show_notification(total_lines)
            
        except subprocess.CalledProcessError as e:
            pass


if __name__ == "__main__":
    app = UpdateNotifier()