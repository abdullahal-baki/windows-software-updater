import re
import subprocess


def check_for_updates():
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
        # print(lines)
        for i, line in enumerate(lines):
            if line.startswith('Name') and 'Id' in line:
                start_index = i + 1
                break
        lines = lines[start_index:]
        updates = []
        
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

                    try:

                        updates.append({
                            'name': parts[0],
                            'id': parts[1],
                            'installed_version': parts[2],
                            'available_version': available_version
                            })
                    except:
                        pass
        print(len(updates))
        return updates
        
        
    except subprocess.CalledProcessError as e:
        pass
check_for_updates()