# Aufheben

Remote administration tool for Windows.

## Overview

Aufheben is a Python-based RAT demonstrating C2 concepts, Windows persistence mechanisms, and post-exploitation techniques. Built to understand how malware operates and how to defend against it. This is basically an old tool i made when i was understanding red team concepts and i thought i'd post it. Enjoy :).

**Note:** This is a learning project. The code intentionally contains limitations (Such as the persistence path being in desktop). Production malware is significantly more complex and stealthy.

## Features

**C2 Communication:**
- AES-CTR encryption (static key for demo)
- Custom binary protocol
- 6-byte length headers
- `0xFEEDBEEFFACE` heartbeat signal
- Multi-client session management
- Automatic reconnection

**Client Capabilities:**
- File upload/download with streaming
- Command execution (visible/hidden)
- Interactive shell (cmd/powershell switching)
- Screenshot capture (PNG format)
- Process enumeration
- Recursive file search
- Keylogger (captures keystrokes)
- Clipboard logger (monitors copy/paste)
- Microphone recording
- Windows event log clearing (System/Application/Security)

**Persistence & Privilege Escalation:**
- Windows Task Scheduler integration
- UAC bypass via fodhelper technique
- Automatic privilege detection
- Mutex-based duplicate prevention
- Remote update mechanism
- Self-destruct with cleanup

**Stealth Features:**
- Background execution (no console window)
- Hidden file placement
- Encrypted communications
- Heartbeat instead of constant polling
- Configurable persistence intervals

## Requirements

```
Python 3.8+
Windows OS
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Server (C2):
```bash
python Aufheben_server.py
```

Server binds to `127.0.0.1:80` by default. Edit source to change.

**Deployment:**
```bash
pyinstaller -F Aufheben_client.py --noconsole --name Aufheben 
```

if you don't have pyinstaller, install it with
```bash
pip install pyinstaller
```

**Important:** Persistence and elevation commands require a compiled `.exe`.
However if you do want to run Aufheben_client.py without compiling to an `.exe` comment out the `self.migrate()` function

## Commands

### Single Session:
```
help              - Command list
cd <path>         - Change directory
ls                - List directory
pwd               - Current directory
download <file>   - Download file
upload <file>     - Upload file
execute <cmd>     - Execute command
  --DISPLAY       - Show output
  --LOG           - Save output
cmd               - Interactive shell
screenshot        - Take screenshot
list_proc         - List processes
search <ext> <path> - Find files
start_keylogger   - Start keylogger
stop_keylogger    - Stop and dump
start_cliplogger  - Start clipboard logger
stop_cliplogger   - Stop and dump
record_mic <sec>  - Record audio
persist           - Add persistence
update <file>     - Update client
self_destruct     - Remove client
check_priv        - Check privileges
clear_logs        - Clear event logs (admin)
bg                - Background session
exit              - Close connection
```

### Multi-Session:
```
sessions          - List active sessions
interact <id>     - Interact with session
elevate <id>      - UAC bypass attempt
elevate_all       - UAC bypass all
kill <id>         - Terminate session
deploy <file>     - Upload/execute on all
  --DISPLAY       - Show output
  --LOG           - Save output
  --DELETE        - Remove after execution
broadcast <cmd>   - Execute on all
start_loggers     - Start all loggers
stop_loggers      - Stop all loggers
update_all <file> - Update all clients
quit              - Exit server
```

## Technical Details

### Migration & Persistence

The `migrate()` function handles initial setup and persistence:

1. **Privilege Detection:** Checks if running with admin rights using `IsUserAnAdmin()`
2. **File Placement:**
   - **Admin:** Copies to `%TEMP%\Aufheben.exe` (hidden system directory)
   - **User:** Copies to `%USERPROFILE%\Desktop\Aufheben.exe` (visible but accessible)
3. **Mutex Check:** Creates mutex `User_Task5@#` to prevent duplicate instances
4. **Task Scheduler Setup:** Registers scheduled task for persistence

**Important:** Migration is currently commented out in `activate()` because:
- Only works when compiled to `.exe` (not Python scripts)
- Task Scheduler requires absolute path to executable
- Python interpreter path handling is complex

To enable: Uncomment `self.migrate()` in the `activate()` method, then compile with PyInstaller.

### IP Address Lookup

The `get_external_ip()` function has a placeholder:

```python
external_ip = b"ip slot here" # IP LOOKUP CODE GOES HERE
```

This is intentionally blank. you can add any ip collection method of your choice

**Why it's blank:** Avoids leaking specific IP lookup services used during development. Also demonstrates that this is demo code, not production malware.

### Encryption

Uses PyCryptodome's AES implementation in CTR mode:

```python
socket_key = b"x\x83\xe1RW\xff\xf1k\xbf\x94\xdef\x88\x8fn\x13:\x9f\xf4\xa5\xf7\x93\xf0l"    # Default key. Place your AES key here 16, 24 or 32 bytes
```

### Task Scheduler Persistence
Two trigger types used:

**Type 7 (TASK_TRIGGER_LOGON):**
- Fires when user logs in
- Used for standard users
- Visible in user's task list

**Type 9 (TASK_TRIGGER_BOOT):**
- Fires at system boot
- Used for admin/SYSTEM
- Runs before user login
- Located in `\Microsoft\` folder (less visible)

**Repetition Interval:** PT5M (every 5 minutes)
- If process dies, task restarts it within 5 minutes
- Ensures persistence despite crashes

### UAC Bypass (Fodhelper)
Exploits Windows 10/11 fodhelper.exe (Manage Optional Features):

1. Modify registry: `HKCU\Software\Classes\ms-settings\Shell\Open\command`
2. Set `DelegateExecute` = "" (empty string)
3. Set default value to payload path
4. Execute `fodhelper.exe` (auto-elevates without UAC prompt)
5. Payload runs with high integrity

### Self-Destruct
The `version_control()` function handles cleanup:

1. Create temporary scheduled task "AufhebenCleanup"
2. Set task to run 5 seconds after creation
3. Task executes: `cmd /c del [current exe] & schtasks /delete /tn AufhebenCleanup /f`
4. Original process exits
5. Task deletes the file and removes itself
6. Clean removal with no traces

**Why scheduled task?** Process can't delete its own running executable. Task waits for process to exit, then deletes file.

### Update Mechanism
Remote update process:

1. Server uploads new executable to `%APPDATA%`
2. Client creates "AufhebenCleanup" task
3. Task deletes old executable, starts new one, removes itself
4. New version begins running
5. Old persistence removed, new persistence created

Allows updating deployed clients without manual access.

## Persistence
Uses Windows Task Scheduler:
- **Admin:** Runs as SYSTEM, stores in `%TEMP%`, trigger type 9 (boot)
- **User:** Runs as current user, stores on Desktop, trigger type 7 (logon)

Repeats every 5 minutes if process dies.

**Limitation:** Only works when compiled to `.exe` (not Python script).

## UAC Bypass

Uses fodhelper technique:
1. Modifies `HKCU\Software\Classes\ms-settings\Shell\Open\command`
2. Triggers `FodHelper`
3. Executes with elevated privileges

Success indicated by trigger type 9 in Task Scheduler.


## Known Issues & Limitations

### 1. Persistence Requires Compilation

**Problem:** `migrate()` is commented out by default

**Why:** Task Scheduler needs absolute path to executable:
```python
action.Path = str(self.persistent_exe)  # Must be .exe, not .py
```

**Solution:** Compile first, then uncomment `self.migrate()` in `activate()`

**Technical reason:** Windows Task Scheduler can't execute Python scripts directly. It needs:
- Valid PE executable
- Absolute path (no relative paths)
- .exe extension


## Final Notes

This tool was built for the purposes of understanding C2 architecture and Windows internals. I hope you find it useful.
If you find bugs or have questions, open an issue. Till then see ya.

This project is for educational/research purposes only.  I'm not responsible if you do illegal stuff with it.  

