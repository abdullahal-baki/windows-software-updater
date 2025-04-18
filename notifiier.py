import subprocess
import re
from plyer import notification
import json
import os

class UpdateNotifier:
    def __init__(self):
        # Initialize variables
        self.updates = []
        self.fake_updates_file = "fake_updates.json"
        self.fake_updates = self._load_fake_updates()
        
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

    def _save_fake_updates(self, package_id, package_version):
        """Save fake updates to the JSON file"""
        try:
            self.fake_updates[package_id] = package_version
            with open(self.fake_updates_file, 'w') as f:
                json.dump(self.fake_updates, f, indent=4)
        except IOError as e:
            pass

    def show_notification(self, updatable_app):
        """Show notification with the number of available updates"""
        notification.notify(
            title="New Version Available!",
            message=f"{updatable_app} Update{'s' if updatable_app != 1 else ''} Available",
            app_name="Software Updater",
            timeout=5
        )

    def check_for_updates(self):
        """Check for available updates"""
        try:
            result = subprocess.run(['winget', 'upgrade', '--accept-source-agreements'], 
                                capture_output=True, text=True, check=True)
            
            # Parse the output (skip header lines and footer)
            lines = result.stdout.split('\n')
            start_index = 0
            # print(lines)
            for i, line in enumerate(lines):
                if line.startswith('Name') and 'Id' in line:
                    start_index = i + 1
                    break
            lines = lines[start_index:]
            self.updates = []
            
            
            for line in lines:
                if line.strip() and not line.startswith('-'):
                    print(line)
                    print(line.split('  '))
                    print()
                    parts = [p.strip() for p in line.split('  ') if p.strip()]
                    if len(parts) >= 4:
                        available_version = parts[3]
                        if 'winget' not in available_version.lower() and re.match(r'.*\d.*', available_version):
                            package_id = parts[1]
                            if package_id in self.fake_updates and self.fake_updates[package_id] == available_version:
                                continue
                            self.updates.append({
                                'name': parts[0],
                                'id': parts[1],
                                'installed_version': parts[2],
                                'available_version': available_version
                            })
            
            if self.updates:
                self.show_notification(len(self.updates))
            
        except subprocess.CalledProcessError as e:
            pass

    def _test_updates(self):
        """Test each update to detect fake updates"""
        for update in self.updates[:]:  # Copy to avoid modifying during iteration
            package_id = update['id']
            package_version = update['available_version']
            try:
                result = subprocess.run(['winget', 'upgrade', '--id', package_id, 
                                       '--accept-package-agreements', '--accept-source-agreements'], 
                                       capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                stdout = e.stdout.strip() if e.stdout else ""
                stderr = e.stderr.strip() if e.stderr else ""
                self._save_fake_updates(package_id, package_version)
                self.updates.remove(update)

if __name__ == "__main__":
    app = UpdateNotifier()