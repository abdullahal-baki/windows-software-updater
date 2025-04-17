import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re

class SoftwareUpdater:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows Software Updater")
        self.root.geometry("900x600")
        
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
        
        self.tree = ttk.Treeview(self.tree_frame, columns=('name', 'current_version', 'new_version', 'update'), 
                                show='headings', yscrollcommand=self.tree_scroll.set)
        self.tree.heading('name', text='Software Name')
        self.tree.heading('current_version', text='Current Version')
        self.tree.heading('new_version', text='Available Version')
        self.tree.heading('update', text='Action')
        
        self.tree.column('name', width=400)
        self.tree.column('current_version', width=200)
        self.tree.column('new_version', width=200)
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
        try:
            result = subprocess.run(['winget', 'upgrade', '--accept-source-agreements'], 
                                  capture_output=True, text=True, check=True)
            
            # Parse the output (skip header lines and footer)
            lines = result.stdout.split('\n')
            # Find the header line and start parsing after it
            start_index = 0
            for i, line in enumerate(lines):
                if line.startswith('Name') and 'Id' in line:
                    start_index = i + 1
                    break
            lines = lines[start_index:]
            self.updates = []
            
            for line in lines:
                if line.strip() and not line.startswith('-'):
                    parts = [p.strip() for p in line.split('  ') if p.strip()]
                    if len(parts) >= 4:
                        # Validate available version (should not be 'winget' or invalid)
                        available_version = parts[3]
                        if available_version.lower() != 'winget' and re.match(r'.*\d.*', available_version):
                            self.updates.append({
                                'name': parts[0],
                                'id': parts[1],
                                'installed_version': parts[2],
                                'available_version': available_version
                            })
            
            # Update GUI in main thread
            self.root.after(0, self._display_updates)
            
        except subprocess.CalledProcessError as e:
            self.root.after(0, self._show_error, f"Error checking for updates: {e.stderr}")
        except FileNotFoundError:
            self.root.after(0, self._show_error, "winget not found. Please install Windows Package Manager.")
        finally:
            self.root.after(0, self._stop_progress)
    
    def _display_updates(self):
        """Display the updates in the treeview"""
        for i, update in enumerate(self.updates):
            self.tree.insert('', tk.END, values=(
                update['name'],
                update['installed_version'],
                update['available_version'],
                'Update'
            ), tags=('update_row',))
        
        # Configure tag for clickable update text
        self.tree.tag_configure('update_row', font=('Helvetica', 10))
        
        if self.updates:
            self.status_label.config(text=f"Found {len(self.updates)} available updates")
            self.update_all_button.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="No updates available")
            self.update_all_button.config(state=tk.DISABLED)
        
        self.check_button.config(state=tk.NORMAL)
    
    def _handle_tree_click(self, event):
        """Handle click events on the Treeview"""
        if self.update_in_progress:
            return
            
        # Identify the clicked item and column
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        if item and column == '#4':  # Update column
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
            
            # Disable all buttons during update
            self.check_button.config(state=tk.DISABLED)
            self.update_all_button.config(state=tk.DISABLED)
            
            # Run update in background thread
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
            self.progress.config(mode='indeterminate')
            self.progress.start()
            
            # Disable all buttons during update
            self.check_button.config(state=tk.DISABLED)
            self.update_all_button.config(state=tk.DISABLED)
            
            # Run update in background thread
            threading.Thread(target=self._update_thread, args=(package_ids, None), daemon=True).start()
    
    def _update_thread(self, package_ids, index):
        """Thread function for updating software"""
        try:
            for package_id in package_ids:
                subprocess.run(['winget', 'upgrade', '--id', package_id, 
                              '--accept-package-agreements', '--accept-source-agreements'], 
                              check=True)
                
                # If updating single package, remove just that one
                if index is not None:
                    self.root.after(0, self._remove_updated_package, index)
                    break
            
            self.root.after(0, self._update_complete, True, "All updates completed successfully")
        except subprocess.CalledProcessError as e:
            self.root.after(0, self._update_complete, False, f"Error updating software: {e.stderr}")
    
    def _remove_updated_package(self, index):
        """Remove an updated package from the treeview"""
        self.tree.delete(self.tree.get_children()[index])
        del self.updates[index]
        
        # If no more updates, disable update all button
        if not self.updates:
            self.update_all_button.config(state=tk.DISABLED)
    
    def _update_complete(self, success, message):
        """Handle update completion"""
        self.update_in_progress = False
        self._stop_progress()
        
        if success:
            self.status_label.config(text=message)
            messagebox.showinfo("Success", message)
        else:
            self.status_label.config(text="Update failed")
            messagebox.showerror("Error", message)
        
        self.check_button.config(state=tk.NORMAL)
        
        # If updates remain, enable update all button
        if self.updates:
            self.update_all_button.config(state=tk.NORMAL)
    
    def _stop_progress(self):
        """Stop the progress bar"""
        self.progress.stop()
        self.progress.config(mode='determinate')
        self.progress['value'] = 0
    
    def _show_error(self, message):
        """Display an error message"""
        self._stop_progress()
        self.status_label.config(text="Error occurred")
        messagebox.showerror("Error", message)
        self.check_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = SoftwareUpdater(root)
    root.mainloop()