import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
from plyer import notification
import json
import os

import requests

class SoftwareUpdater:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows Software Updater")
        self.root.geometry("1200x600")
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat")
        self.style.configure("Title.TLabel", font=('Helvetica', 16, 'bold'))
        self.style.configure("Subtitle.TLabel", font=('Helvetica', 12))
        self.style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(self.main_frame, text="Windows Software Updater", style="Title.TLabel").grid(row=0, column=0, columnspan=2, pady=10)
        
        # Check for updates button
        self.check_button = ttk.Button(self.main_frame, text="Check for Updates", command=self.check_for_updates)
        self.check_button.grid(row=1, column=0, pady=10, sticky=tk.W)
        
        # Update all button (initially disabled)
        self.update_all_button = ttk.Button(self.main_frame, text="Update All", state=tk.DISABLED, command=self.update_all)
        self.update_all_button.grid(row=1, column=1, pady=10, sticky=tk.E)
        
        # Status label
        self.status_label = ttk.Label(self.main_frame, text="Click 'Check for Updates' to begin", style="Subtitle.TLabel")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(self.main_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        # Treeview for updates
        self.tree_frame = ttk.Frame(self.main_frame)
        self.tree_frame.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
        
        # Create a scrollbar
        self.tree_scroll = ttk.Scrollbar(self.tree_frame)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(self.tree_frame, columns=('name', 'current_version', 'new_version','file_size', 'update'), 
                                show='headings', yscrollcommand=self.tree_scroll.set)
        self.tree.heading('name', text='Software Name')
        self.tree.heading('current_version', text='Current Version')
        self.tree.heading('new_version', text='Available Version')
        self.tree.heading('file_size', text='New Version Size')
        self.tree.heading('update', text='Action')
        
        self.tree.column('name', width=400)
        self.tree.column('current_version', width=200)
        self.tree.column('new_version', width=200)
        self.tree.column('file_size', width=100)
        self.tree.column('update', width=100)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll.config(command=self.tree.yview)
        
        # Bind click event for the update column
        self.tree.bind('<Button-1>', self._handle_tree_click)
        
        # Configure grid weights
        self.main_frame.grid_rowconfigure(4, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        
        # Initialize variables
        self.updates = []
        self.update_in_progress = False
        self.fake_updates_file = "fake_updates.json"
        self.fake_updates = self._load_fake_updates()
        
        # Automatically check for updates on startup
        self.check_for_updates()

    def _load_fake_updates(self):
        """Load fake updates from the JSON file"""
        if os.path.exists(self.fake_updates_file):
            try:
                with open(self.fake_updates_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_fake_updates(self):
        """Save fake updates to the JSON file"""
        try:
            with open(self.fake_updates_file, 'w') as f:
                json.dump(self.fake_updates, f, indent=4)
        except IOError as e:
            self._show_error(f"Error saving fake updates: {e}")

    def show_notification(self, updatable_app):
        """Show notification with the number of available updates"""
        notification.notify(
            title="New Version Available!",
            message=f"{updatable_app} Update{'s' if updatable_app != 1 else ''} Available",
            app_name="Software Updater",
            timeout=5
        )

    def check_for_updates(self):
        """Check for available updates in a separate thread"""
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return
            
        self.check_button.config(state=tk.DISABLED)
        self.status_label.config(text="Checking for updates...")
        self.progress.config(mode='indeterminate')
        self.progress.start()
        
        # Clear previous results
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Run in background thread to prevent GUI freezing
        threading.Thread(target=self._check_for_updates_thread, daemon=True).start()
        
    def _check_for_updates_thread(self):
        """Thread function for checking updates"""
        def run_command_silently(command):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                command,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
        def get_file_size(id):
            result = run_command_silently(['winget', 'show', id])
            
            match = re.search(r'Installer Url:\s*(https?://[^\s]+\.exe)', result.stdout, re.IGNORECASE)
            if match:
                link = match.group(1)
                response = requests.head(link, allow_redirects=True, timeout=10)

                # Fallback to GET if HEAD doesn't return Content-Length
                if 'Content-Length' not in response.headers:
                    response = requests.get(link, stream=True, timeout=10)
                
                size_bytes = int(response.headers.get('Content-Length', 0))
                size_mb = round(size_bytes / (1024 * 1024), 2)
                return size_mb
            return None
            
            
            
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
            for line in lines:
                if line.strip() and not line.startswith('-'):
                    line = line.replace('winget', '')
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
                        package_id = parts[1]
                        if package_id in self.fake_updates and self.fake_updates[package_id] == available_version:
                            continue
                        else:
                            file_size = get_file_size(package_id)
                            self.updates.append({
                                'name': parts[0],
                                'id': parts[1],
                                'installed_version': parts[2],
                                'available_version': available_version,
                                'file_size': file_size
                            })
            
            self.root.after(0, self._display_updates)
            
        except subprocess.CalledProcessError as e:
            self.root.after(0, self._show_error, f"Error checking for updates: {e.stderr}")
        except FileNotFoundError:
            self.root.after(0, self._show_error, "winget not found. Please install Windows Package Manager.")
        finally:
            self.root.after(0, self._stop_progress)
    
    def _display_updates(self):
        """Display the updates in the treeview and show notification"""
        for i, update in enumerate(self.updates):
            self.tree.insert('', tk.END, values=(
                update['name'],
                update['installed_version'],
                update['available_version'],
                f"{update['file_size']} MB" if update['file_size'] else "N/A",
                'Update'
            ), tags=('update_row',))
        
        self.tree.tag_configure('update_row', font=('Helvetica', 10))
        
        if self.updates:
            self.status_label.config(text=f"Found {len(self.updates)} available updates")
            self.update_all_button.config(state=tk.NORMAL)
            # Show notification only if there are updates
            self.show_notification(len(self.updates))
        else:
            self.status_label.config(text="No updates available")
            self.update_all_button.config(state=tk.DISABLED)
        
        self.check_button.config(state=tk.NORMAL)
    
    def _handle_tree_click(self, event):
        """Handle click events on the Treeview"""
        if self.update_in_progress:
            return
            
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        if item and column == '#5':
            index = int(self.tree.index(item))
            self.update_single(index)
    
    def update_single(self, index):
        """Update a single software package"""
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return
            
        package_id = self.updates[index]['id']
        package_name = self.updates[index]['name']
        
        if messagebox.askyesno("Confirm Update", f"Update {package_name} to version {self.updates[index]['available_version']}?"):
            self.update_in_progress = True
            self.status_label.config(text=f"Updating {package_name}...")
            self.progress.config(mode='indeterminate')
            self.progress.start()
            
            self.check_button.config(state=tk.DISABLED)
            self.update_all_button.config(state=tk.DISABLED)
            
            threading.Thread(target=self._update_thread, args=([package_id], index), daemon=True).start()
    
    def update_all(self):
        """Update all available software"""
        if self.update_in_progress:
            messagebox.showwarning("Warning", "An update is already in progress")
            return
            
        if not self.updates:
            messagebox.showinfo("Info", "No updates available")
            return
            
        package_ids = [update['id'] for update in self.updates]
        package_names = "\n".join([update['name'] for update in self.updates])
        
        if messagebox.askyesno("Confirm Update", f"Update all {len(self.updates)} packages?\n\n{package_names}"):
            self.update_in_progress = True
            self.status_label.config(text="Updating all software...")
            self.progress.config(mode='determinate', maximum=len(package_ids))
            self.progress['value'] = 0
            
            self.check_button.config(state=tk.DISABLED)
            self.update_all_button.config(state=tk.DISABLED)
            
            threading.Thread(target=self._update_thread, args=(package_ids, None), daemon=True).start()
    
    def _update_thread(self, package_ids, index):
        """Thread function for updating software"""
        def run_command_silently(command):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                command,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
    
        try:
            success = True
            error_message = ""
            for i, package_id in enumerate(package_ids):
                # Use correct winget command to apply the update
                command = ['winget', 'upgrade', package_id, '--accept-source-agreements']
                result = run_command_silently(command)
                
                stdout = result.stdout.strip() if result.stdout else ""
                stderr = result.stderr.strip() if result.stderr else ""
                combined_output = (stdout + " " + stderr).lower()
                
                # Check for success
                if result.returncode == 0 or "successfully upgraded" in combined_output.lower():
                    if index is not None:
                        # Single update case
                        self.root.after(0, self._remove_updated_package, index)
                        self.root.after(0, self._stop_progress)
                        self.root.after(0, self._update_complete, True, f"Successfully updated {package_id}")
                        return  # Exit after single update
                    else:
                        # Batch update case
                        update_index = next((idx for idx, update in enumerate(self.updates) if update['id'] == package_id), None)
                        if update_index is not None:
                            self.root.after(0, self._remove_updated_package, update_index)
                            self.root.after(0, lambda: self.progress.config(value=i+1))
                else:
                    if "no package found" in combined_output or "not installed" in combined_output:
                        if index is not None:
                            # Single fake update case
                            self.root.after(0, self._handle_fake_update, index, package_id)
                            self.root.after(0, self._stop_progress)
                            return
                        else:
                            # Batch fake update case
                            update_index = next((idx for idx, update in enumerate(self.updates) if update['id'] == package_id), None)
                            if update_index is not None:
                                self.root.after(0, self._handle_fake_update, update_index, package_id)
                    else:
                        success = False
                        error_message = stderr or stdout or "Unknown error occurred"
                        if index is not None:
                            self.root.after(0, self._handle_fake_update, index, package_id)
                            self.root.after(0, self._stop_progress)
                            self.root.after(0, self._update_complete, False, f"Error updating {package_id}: {error_message}")
                            return
                        else:
                            self.root.after(0, lambda: self.status_label.config(text=f"Error updating {package_id}"))
            
            # If we get here, it's a batch update that completed
            if success:
                self.root.after(0, self._stop_progress)
                self.root.after(0, self._update_complete, True, "All updates completed successfully")
        
        except subprocess.CalledProcessError as e:
            stdout = e.stdout.strip() if e.stdout else ""
            stderr = e.stderr.strip() if e.stderr else ""
            error_message = stderr or stdout or "Unknown error occurred"
            self.root.after(0, self._stop_progress)
            self.root.after(0, self._update_complete, False, f"Error updating software: {error_message}")
        
        except Exception as e:
            self.root.after(0, self._stop_progress)
            self.root.after(0, self._update_complete, False, f"Unexpected error: {e}")

    def _handle_fake_update(self, index, package_id):
        """Handle a fake update by removing it and recording it"""
        try:
            package_name = self.updates[index]['name']
            package_version = self.updates[index]['available_version']
            
            self.fake_updates[package_id] = package_version
            self._save_fake_updates()
            
            self._remove_updated_package(index)
            
            self.update_in_progress = False
            self._stop_progress()
            self.status_label.config(text=f"Removed fake update for {package_name}")
            
            self.check_button.config(state=tk.NORMAL)
            
            if self.updates:
                self.update_all_button.config(state=tk.NORMAL)
        except Exception as e:
            self._stop_progress()
            self._update_complete(False, f"Error handling fake update: {e}")

    def _remove_updated_package(self, index):
        """Remove an updated package from the treeview"""
        try:
            self.tree.delete(self.tree.get_children()[index])
            del self.updates[index]
            
            if not self.updates:
                self.update_all_button.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Error removing package: {e}")

    def _update_complete(self, success, message):
        """Handle update completion"""
        self.update_in_progress = False
        self._stop_progress()
        
        if success:
            self.status_label.config(text=message)
            if not self.updates:  # Only show success message if all updates are done
                messagebox.showinfo("Success", message)
        else:
            self.status_label.config(text="Update failed")
            messagebox.showerror("Error", message)
        
        self.check_button.config(state=tk.NORMAL)
        
        if self.updates:
            self.update_all_button.config(state=tk.NORMAL)
        else:
            self.update_all_button.config(state=tk.DISABLED)

    def _stop_progress(self):
        """Stop the progress bar"""
        try:
            self.progress.stop()
            self.progress.config(mode='determinate', value=0)
        except Exception as e:
            print(f"Error stopping progress bar: {e}")

    def _show_error(self, message):
        """Display an error message"""
        self._stop_progress()
        self.status_label.config(text="Error occurred")
        messagebox.showerror("Error", message)
        self.check_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_path, 'icon.ico')
        root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error loading icon: {e}")
    
    app = SoftwareUpdater(root)
    root.mainloop()