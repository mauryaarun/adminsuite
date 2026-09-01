================================================================================
                        ADMIN SUITE v6 — README
================================================================================
   SSH Client · DB GUI · Automation Center
================================================================================

================================================================================
  TABLE OF CONTENTS
================================================================================

  1.  Overview
  2.  Feature Summary
  3.  Screenshots / UI Layout
  4.  Requirements
  5.  Installation
  6.  First Launch
  7.  SSH Terminal Guide
  8.  SFTP File Manager Guide
  9.  SysAdmin Dashboard Guide
  10. Database Manager Guide
  11. Ansible Center Guide
  12. VPN Integration
  13. Profiles & Key Management
  14. Keyboard Shortcuts
  15. Theming
  16. Session Logging & Restore
  17. Configuration Files
  18. Project Structure
  19. Troubleshooting
  20. Known Limitations
  21. Contributing
  22. License & Disclaimer

================================================================================
  1. OVERVIEW
================================================================================

Admin Suite v4 is a single-window, tab-based desktop application that unifies
the daily workflow of a Linux system administrator into one cohesive tool:

  • SSH Terminal      — Full xterm.js-powered interactive terminal over SSH,
                        with jump-host support, split panes, broadcast mode,
                        latency monitoring, and auto-reconnect.

  • SFTP Client       — Dual-pane local/remote file browser with drag-and-drop
                        upload/download, recursive directory transfers, chmod
                        editor, remote text editor, and remote grep search.

  • SysAdmin Dashboard— Live system overview (CPU, RAM, disks, network,
                        journal, cron, services, processes) executed over SSH
                        or locally. Service start/stop/restart controls.

  • Database Manager  — Multi-backend (MySQL, SQLite, PostgreSQL) query
                        editor with SQL autocomplete, syntax highlighting,
                        schema browser tree, query history, favorites,
                        CSV/JSON export, and EXPLAIN support.

  • Ansible Center    — Ad-hoc command runner and playbook executor with
                        live log output, inventory auto-built from SSH
                        profiles, become/sudo toggle, and execution history.

  • VPN Integration   — Cisco AnyConnect / Secure Client connect/disconnect
                        with status indicator in the top toolbar.

The application stores credentials in the OS keyring (via Python keyring),
persists profiles and settings to JSON files in the home directory, and
supports themable UI (Breeze Dark, Light, Nord, Dracula) with matching
terminal color schemes.

================================================================================
  2. FEATURE SUMMARY
================================================================================

SSH TERMINAL
  - Interactive xterm.js terminal rendered inside QWebEngineView
  - Password, SSH Key, and SSH Agent authentication
  - Jump host (ProxyJump) routing
  - Split terminal panes (horizontal / vertical) from same profile
  - Broadcast mode: type once, sent to ALL open terminals (F8)
  - Latency monitor (keepalive-based, color-coded)
  - Auto-reconnect with configurable retry count and capped backoff
  - Session recording to ~/.admin_suite_sessions/*.log
  - In-terminal search (Ctrl+F), clear, font size +/-, reconnect buttons
  - Local shell tab (bash PTY) for commands without SSH

SFTP FILE MANAGER
  - Dual-pane layout: Local | Remote
  - Drag-and-drop upload/download between panes
  - Recursive directory upload and download
  - Transfer queue with progress bar
  - chmod permission editor (checkbox + octal preview)
  - Remote text file viewer/editor (save back over SFTP)
  - Remote grep search dialog (pattern + path → results table)
  - Context menus: upload, download, edit, chmod, delete, mkdir, copy path
  - Multi-selection support

SYSADMIN DASHBOARD
  - Overview: hostname, kernel, uptime, load, memory, CPU, sensors
  - Users: parsed /etc/passwd table (user, UID, GID, home, shell)
  - Services: systemctl list with start/stop/restart/enable/disable buttons
  - Processes: ps aux sorted by CPU, rendered as table
  - Storage: lsblk, df, swap, LVM, NFS mounts
  - Network: interfaces, routes, listening sockets, DNS, firewall
  - Journal: last 200 journal/syslog lines
  - Cron: system crontab, cron.d, user crontab
  - Works over SSH profile or locally (profile = None)
  - Optional sudo prefix checkbox

DATABASE MANAGER
  - Backends: MySQL (PyMySQL), SQLite (stdlib), PostgreSQL (psycopg2)
  - SSH tunnel support via sshtunnel for remote databases
  - Schema browser tree: Databases → Tables → Columns
  - SQL editor with syntax highlighting and keyword/table autocomplete
  - Execute with F5 shortcut
  - EXPLAIN query button
  - Query history (persisted, searchable)
  - Query favorites (named, persisted)
  - CSV and JSON export of result sets
  - Context menus: SELECT, COUNT, SHOW COLUMNS, SHOW INDEX,
    INSERT generator, TRUNCATE, DROP (with confirmation)
  - Table detail tab: Schema view + Data view with LIMIT control
  - DB profile management with per-profile credentials in keyring

ANSIBLE CENTER
  - Inventory auto-built from SSH profiles (password or key auth)
  - Ad-hoc module runner: ping, shell, command, apt, yum, copy, file,
    service, systemd, reboot, setup, raw
  - Run ad-hoc in GUI output panel or in a terminal tab
  - Playbook browser: scan a directory for *.yml / *.yaml files
  - Playbook runner with --limit and --extra-vars support
  - Become (sudo) toggle with become password
  - Live streaming output for both ad-hoc and playbooks
  - Execution history (timestamp, kind, target, exit code)
  - Connection test for selected hosts

VPN INTEGRATION
  - Cisco AnyConnect / Secure Client CLI integration
  - Connect with scripted stdin (cert password + user password + confirm)
  - Disconnect command
  - Status check on startup and after connect/disconnect
  - Configurable CLI path and VPN host in Connection Manager

PROFILES & KEY MANAGEMENT
  - SSH profile CRUD with groups, tags, favorites, auto-connect
  - Jump host configuration per profile
  - Initial command per profile (e.g., "sudo su -")
  - SSH key manager: list keys in ~/.ssh, generate RSA 2048/4096 keys
  - Import ~/.ssh/config as profiles (Host, Hostname, User, Port,
    IdentityFile parsed)
  - Credentials stored in OS keyring (keyring Python package)
  - Profile tree with ping status indicators (green/red/gray)

UI / UX
  - Command palette (Ctrl+K): fuzzy search across all actions & profiles
  - Notification center with toast popups
  - 4 UI themes: Breeze Dark, Light, Nord, Dracula
  - 6 terminal themes: dark, light, nord, dracula, solarized, monokai
  - Persistent window geometry
  - Session restore on launch (reopen last terminals)
  - Reopen closed tab (Ctrl+Shift+T)
  - Sidebar with profile filter, DB profiles, recent connections
  - Tab context menu: rename, close, close others, close right
  - Movable and closable tabs

================================================================================
  3. UI LAYOUT
================================================================================

┌──────────────────────────────────────────────────────────────────────────┐
│  SIDEBAR (270px)  │  NAVBAR: Palette | Broadcast | VPN | 🔔 | Clock    │
│  ─────────────────┼──────────────────────────────────────────────────────│
│  🛠 ADMIN SUITE   │                                                      │
│  🔍 Filter...     │  TAB BAR                                             │
│                   │  ┌────────┬────────┬────────┬────────┬─────────┐    │
│  PROFILES         │  │🗄 DB   │🤖 Ans  │🐚 ssh1 │📁 sftp │⚠ Debug  │    │
│  ├ 📁 Default     │  └────────┴────────┴────────┴────────┴─────────┘    │
│  │ ├ 🟢 web01     │                                                      │
│  │ ├ 🔴 db01      │  TAB CONTENT AREA                                    │
│  │ └ ⚪ staging    │  (Terminal / SFTP / Dashboard / DB / Ansible)       │
│  ├ ⭐ Favorites   │                                                      │
│  └ 📁 prod        │                                                      │
│  [+][✏][🗑][📡]   │                                                      │
│                   │                                                      │
│  DATABASES        │                                                      │
│  🗄 prod-mysql    │                                                      │
│  🗄 local-sqlite  │                                                      │
│  [+][✏][🗑]       │                                                      │
│                   │                                                      │
│  RECENT           │                                                      │
│  web01            │                                                      │
│                   │                                                      │
│  TOOLS            │                                                      │
│  ⚡ Local Shell    │                                                      │
│  📝 Snippets      │                                                      │
│  🔑 Key Manager   │                                                      │
│  📥 Import Config │                                                      │
│  🎬 Recordings    │                                                      │
│  🎨 Themes        │                                                      │
│  ⚙️ Conn Manager  │                                                      │
└──────────────────────────────────────────────────────────────────────────┘
│  STATUS BAR: Ready — double-click a profile · Ctrl+K palette ...        │
└──────────────────────────────────────────────────────────────────────────┘

================================================================================
  4. REQUIREMENTS
================================================================================

CORE (Required)
  Python          >= 3.10
  PyQt6           >= 6.5.0
  PyQt6-WebEngine >= 6.5.0
  paramiko        >= 3.0.0
  sshtunnel       >= 0.4.0
  PyMySQL         >= 1.1.0
  keyring         >= 24.0.0

OPTIONAL
  psycopg2-binary >= 2.9.9    (PostgreSQL backend)
  ansible         >= 9.0.0    (Ansible Center)

SYSTEM DEPENDENCIES (Linux)
  - bash          (local shell, remote commands)
  - ssh           (underlying SSH connectivity)
  - xdg-open      (open session log folder)
  - pty, fcntl    (local terminal — Linux/macOS only)

OPTIONAL SYSTEM TOOLS (for SysAdmin Dashboard)
  - systemctl, hostnamectl, lscpu, free, uptime
  - lsblk, df, swapon, ip, ss
  - journalctl or /var/log/syslog
  - lm-sensors (sensors command)

VPN (Optional)
  - Cisco AnyConnect / Secure Client CLI
    Default path: /opt/cisco/secureclient/bin/vpn

INTERNET ACCESS (First Launch Only)
  xterm.js assets are downloaded from cdn.jsdelivr.net on first run
  and cached to ~/.cache/admin_suite_xterm/. No internet needed after.

================================================================================
  5. INSTALLATION
================================================================================

STEP 1 — Create a virtual environment (recommended):

    python3 -m venv ~/.venvs/adminsuite
    source ~/.venvs/adminsuite/bin/activate

STEP 2 — Install core dependencies:

    pip install PyQt6 PyQt6-WebEngine paramiko sshtunnel PyMySQL keyring

STEP 3 — Install optional dependencies:

    # PostgreSQL support
    pip install psycopg2-binary

    # Ansible Center
    pip install ansible

STEP 4 — Or install from requirements.txt:

    pip install -r requirements.txt

STEP 5 — Run the application:

    python linuxadmin.py

STEP 6 — (Optional) Create a desktop shortcut:

    [Desktop Entry]
    Name=Admin Suite v4
    Exec=/home/YOURUSER/.venvs/adminsuite/bin/python /path/to/linuxadmin.py
    Icon=/path/to/icon.png
    Type=Application
    Categories=System;Network;Database;

================================================================================
  6. FIRST LAUNCH
================================================================================

1. The application window opens with the sidebar and three pinned tabs:
   Database Manager, Ansible Center, and Debug.

2. On first launch, xterm.js assets are downloaded (~500 KB). Ensure
   internet connectivity. Assets are cached for future launches.

3. Add your first SSH profile:
   - Click ➕ in the sidebar PROFILES section, or
   - Use Command Palette (Ctrl+K) → "Add Profile"

4. Fill in: Name, SSH Host, Username, Port, Auth method.

5. Double-click the profile in the tree to open a terminal tab.

6. Configure global settings via ⚙️ Connection Manager (Ctrl+,):
   - Database connection (backend, host, tunnel)
   - Terminal preferences (font size, theme, auto-reconnect)
   - VPN CLI path and host
   - Ansible playbook directory

================================================================================
  7. SSH TERMINAL GUIDE
================================================================================

OPENING A TERMINAL
  - Double-click a profile in the sidebar tree
  - Right-click profile → "Open Terminal"
  - Ctrl+T (opens selected profile or prompts)
  - Command Palette → "Connect: <profile name>"

TERMINAL TOOLBAR
  ● Status    — Shows connection state (Connecting / Connected / Error)
  ⏱ Latency  — Round-trip time via SSH keepalive (color-coded)
  📝 Log      — Session log filename (click tooltip for full path)
  🔍 Search   — Toggle in-terminal search (Ctrl+F)
  🧹 Clear    — Clear terminal screen
  🔄 Reconnect— Force reconnect (resets retry counter)
  A+ / A-     — Increase/decrease terminal font size

SPLIT TERMINALS
  - Right-click profile → "Split Terminal"
  - Use "Split Right" / "Split Down" buttons to add panes
  - All panes share the same profile/connection settings

BROADCAST MODE (F8)
  - Opens a confirmation dialog listing terminal count
  - When ON, everything typed in any terminal is mirrored to ALL others
  - Useful for running the same command on multiple servers
  - Button turns yellow/warning color when active
  - Press F8 again to disable

LOCAL SHELL
  - Sidebar → Tools → "⚡ Local Shell"
  - Opens an interactive bash PTY (Linux/macOS only)
  - Useful for local commands without SSH overhead

SESSION LOGGING
  - Enabled by default (Connection Manager → Terminal → checkbox)
  - Logs saved to ~/.admin_suite_sessions/<name>_<timestamp>.log
  - Contains both input and output with session start/end markers
  - View via Sidebar → Tools → "🎬 Session Recordings"

AUTO-RECONNECT
  - Enabled by default; up to 3 retries with increasing delay (capped 10s)
  - Disable in Connection Manager → Terminal → uncheck "Auto-reconnect"
  - Manual reconnect always available via 🔄 button

================================================================================
  8. SFTP FILE MANAGER GUIDE
================================================================================

OPENING SFTP
  - Right-click profile → "Open SFTP"
  - Command Palette → "SFTP: <profile name>"

LAYOUT
  Left panel  = Local filesystem (starts at ~)
  Right panel = Remote filesystem (starts at /)
  Both panels have: path bar, ⬆ up, 🔄 refresh, file tree

TRANSFERRING FILES
  Method 1: Double-click a file in either panel
  Method 2: Select file → click "Upload Selected" / "Download Selected"
  Method 3: Drag and drop between panels
  Method 4: Right-click file → Upload/Download from context menu

DIRECTORY TRANSFERS
  - Right-click a directory → "Upload Dir to Remote" / "Download Dir to Local"
  - Recursive transfer handles nested directories automatically
  - Transfer queue processes multiple files sequentially with progress bar

REMOTE FILE EDITOR
  - Right-click a remote file → "Open in Editor"
  - Opens in a new tab with syntax-aware plain text editor
  - Ctrl+S saves back to remote via SFTP
  - Modified indicator shows unsaved changes

CHMOD EDITOR
  - Right-click remote file → "Permissions (chmod)"
  - Checkbox UI for user/group/other × r/w/x
  - Live octal preview (e.g., 0755)
  - Apply sends chmod over SFTP

REMOTE SEARCH (GREP)
  - Click "🔎 Remote Search..." button
  - Enter pattern and search path
  - Results shown as File | Line | Match table
  - Uses: grep -rnI --color=never -m 300

================================================================================
  9. SYSADMIN DASHBOARD GUIDE
================================================================================

OPENING THE DASHBOARD
  - Right-click profile → "SysAdmin Dashboard"
  - Command Palette → "SysAdmin: <profile name>"
  - For local system: Command Palette → "Open SysAdmin Dashboard"

SECTIONS (left navigation)
  Overview   — hostname, kernel, uptime, load, memory, CPU, sensors
  Users      — /etc/passwd parsed into table
  Services   — systemctl list-units with action buttons
  Processes  — ps aux sorted by CPU usage
  Storage    — lsblk, df, swap, LVM, NFS mounts
  Network    — interfaces, routes, listening ports, DNS, firewall
  Journal    — last 200 journal/syslog entries
  Cron       — system crontab, cron.d, user crontab

SERVICE MANAGEMENT
  - Navigate to "Services" section
  - Click a service row to select it
  - Use Start / Stop / Restart / Enable / Disable buttons
  - Check "Use sudo" if elevated privileges are needed
  - Confirmation dialog before execution

SUDO CHECKBOX
  - When checked, prepends "sudo " to service commands
  - Useful when SSH user is non-root

================================================================================
  10. DATABASE MANAGER GUIDE
================================================================================

CONNECTION SETUP
  Option A: Global settings via Connection Manager (Ctrl+,) → Database tab
  Option B: DB Profiles in sidebar (recommended for multiple databases)

  For DB Profiles:
  - Click ➕ in the DATABASES sidebar section
  - Configure: Name, Backend, Host, Port, User, Password, Schema
  - Optional: SSH tunnel (SSH host/user/pass)
  - SQLite: browse to .db/.sqlite file instead of host/port

CONNECTING
  - Click "🔌 Connect Database" button, or
  - Double-click a DB profile in sidebar, or
  - Right-click DB profile → "Connect"

SCHEMA BROWSER
  - Tree structure: 🗄 Database → 📋 Tables → 🔢 Columns
  - Click ▶ to expand (lazy-loads tables/columns)
  - Right-click for quick queries: SELECT, COUNT, SHOW COLUMNS,
    SHOW INDEX, INSERT generator, TRUNCATE, DROP

SQL EDITOR
  - Syntax highlighting (keywords, strings, numbers, comments)
  - Autocomplete: SQL keywords + loaded table/column names
  - F5 to execute
  - EXPLAIN button prepends EXPLAIN to current query
  - Save queries to Favorites for reuse

RESULTS
  - Displayed in table with alternating row colors
  - NULL values shown as "NULL"
  - Row count and execution time shown below results
  - Export results to CSV or JSON via toolbar buttons

TABLE DETAIL TAB
  - Double-click a table in schema tree
  - Two inner tabs: 📐 Schema (column definitions) and 📊 Data
  - Data tab has configurable LIMIT (1–10000)
  - Export table data to CSV

SUPPORTED BACKENDS
  MySQL       — via PyMySQL, supports SHOW DATABASES/TABLES/COLUMNS
  SQLite      — via Python stdlib, PRAGMA table_info
  PostgreSQL  — via psycopg2 (optional install), information_schema

================================================================================
  11. ANSIBLE CENTER GUIDE
================================================================================

PREREQUISITES
  - ansible must be installed: pip install ansible
  - SSH profiles configured in the sidebar

HOST SELECTION
  - Left panel lists all SSH profiles
  - Multi-select hosts (Ctrl+click or "Select All")
  - "Test Selected" verifies SSH connectivity
  - "Become (sudo)" checkbox adds ansible_become=yes

AD-HOC COMMANDS
  - Select module from dropdown: ping, shell, command, apt, yum, etc.
  - Enter arguments (e.g., "df -h" for shell, "name=nginx state=restarted")
  - "Run" executes in GUI output panel
  - "Run in Terminal" opens in a local terminal tab
  - Inventory is auto-generated as a temp INI file

PLAYBOOKS
  - Set playbook directory in Connection Manager → Ansible tab
  - Or browse and scan directly in the Playbooks tab
  - Select a playbook from the list
  - Optional: --limit and --extra-vars
  - "Run Playbook" streams output live

EXECUTION HISTORY
  - "History" tab shows: timestamp, kind (ad-hoc/playbook), target, exit code
  - Exit code 0 = success (green), non-zero = failure (red)
  - Clear history button available

INVENTORY GENERATION
  - Auto-built from selected SSH profiles
  - Supports password auth (ansible_password) and key auth
  - Adds StrictHostKeyChecking=no for automation
  - Temp file is deleted after execution

================================================================================
  12. VPN INTEGRATION
================================================================================

SUPPORTED CLIENT
  Cisco AnyConnect / Cisco Secure Client CLI
  Default path: /opt/cisco/secureclient/bin/vpn

CONFIGURATION
  Connection Manager (Ctrl+,) → VPN tab:
  - VPN CLI Path: full path to the vpn binary
  - VPN Host: VPN gateway hostname or IP
  - Cert Password: certificate password (if applicable)
  - Password: user authentication password

USAGE
  - Click "⚡ VPN Connect" in the top toolbar
  - Click "🔌 VPN Off" to disconnect
  - Status indicator shows: Connected ✅ / Disconnected / Error ❌ / n/a
  - Status is checked automatically on application startup

HOW IT WORKS
  The application pipes credentials via stdin:
    <cert_password>\n<user_password>\ny\n
  to: vpn -s connect <vpn_host>
  Disconnect uses: vpn -s disconnect
  Status check uses: vpn status (parses "state: Connected")

CUSTOM VPN CLIENTS
  For non-Cisco VPN clients, modify the connect_vpn() and
  disconnect_vpn() methods in MainWindow to match your CLI.

================================================================================
  13. PROFILES & KEY MANAGEMENT
================================================================================

SSH PROFILE FIELDS
  Name              — Display name (unique)
  Group / Folder    — Organizational grouping in sidebar tree
  Tags              — Comma-separated for filtering
  Favorite          — Pinned to ⭐ Favorites group
  SSH Host          — Hostname or IP
  Username          — SSH login user
  Port              — SSH port (default 22)
  Auth Method       — Password or SSH Key
  Password          — SSH password or key passphrase
  SSH Key Path      — Path to private key file
  Use SSH Agent     — Delegate auth to ssh-agent
  Initial Command   — Command sent after connect (e.g., "sudo su -")
  Auto-connect      — Connect when session is restored
  Jump Host         — Route through intermediary SSH host
    Jump Host/Port/User/Pass — Jump host credentials

PROFILE OPERATIONS
  ➕ Add      — Opens profile dialog
  ✏️ Edit     — Edit selected profile
  🗑️ Delete   — Delete with confirmation
  📡 Ping     — Test connectivity to all profiles (async)
  Right-click — Terminal, SFTP, SysAdmin, Split, Remote Search, Test

SSH KEY MANAGER
  Sidebar → Tools → "🔑 SSH Key Manager"
  - Lists all key pairs in ~/.ssh/ (by .pub file)
  - Select a key to view its public part
  - Generate new RSA keys (2048 or 4096 bits)
  - Keys saved with 0600 permissions

IMPORT ~/.ssh/config
  Sidebar → Tools → "📥 Import ~/.ssh/config"
  Parses: Host, Hostname, User, Port, IdentityFile
  Skips wildcard hosts (*)
  Imports as new profiles (won't overwrite existing)

CREDENTIAL STORAGE
  All passwords are stored in the OS keyring:
  - Linux: Secret Service (GNOME Keyring / KWallet)
  - macOS: Keychain
  - Windows: Windows Credential Locker
  Never stored in plain text JSON files.

================================================================================
  14. KEYBOARD SHORTCUTS
================================================================================

  Shortcut          Action
  ─────────────────────────────────────────────────────────
  Ctrl+K            Open Command Palette
  Ctrl+Shift+P      Open Command Palette (alternate)
  Ctrl+T            New Terminal (selected profile)
  Ctrl+W            Close current tab
  Ctrl+Shift+T      Reopen last closed tab
  Ctrl+B            Toggle sidebar visibility
  Ctrl+,            Open Connection Manager
  F8                Toggle Broadcast Mode
  F5                Execute SQL query (Database Manager)
  Ctrl+F            Search in terminal
  Ctrl+S            Save file (Remote Editor)

  Terminal-specific:
  A+                Increase font size
  A-                Decrease font size
  🔍 button         Toggle terminal search
  🧹 button         Clear terminal
  🔄 button         Reconnect terminal

================================================================================
  15. THEMING
================================================================================

UI THEMES (Interface)
  Breeze Dark  — Default dark theme (blue accent)
  Light        — Clean light theme (blue accent)
  Nord         — Nord color palette (cyan accent)
  Dracula      — Dracula color palette (purple accent)

  Change via: Sidebar → Tools → "🎨 Themes"
  Or: Command Palette → "Theme Manager"

TERMINAL THEMES (xterm.js)
  dark, light, nord, dracula, solarized, monokai

  Change via: Connection Manager → Terminal → Terminal Theme
  Matching terminal theme is auto-selected when UI theme changes.

  Terminal theme applies to NEW terminal tabs only.
  Existing tabs retain their original theme.

================================================================================
  16. SESSION LOGGING & RESTORE
================================================================================

SESSION LOGGING
  Location: ~/.admin_suite_sessions/
  Format:   <profile_name>_<YYYYMMDD_HHMMSS>.log
  Content:  All terminal I/O with start/end timestamps
  Toggle:   Connection Manager → Terminal → checkbox

SESSION RESTORE
  On close, open terminal profile names are saved to:
    ~/.admin_suite_v4_last_session.json
  On next launch, a dialog offers to restore those sessions.

SESSION LOG VIEWER
  Sidebar → Tools → "🎬 Session Recordings"
  - Lists all recorded sessions (newest first)
  - Select to view content
  - "Open Folder" opens the log directory in file manager

================================================================================
  17. CONFIGURATION FILES
================================================================================

All files are stored in the user's home directory (~):

  FILE                                    PURPOSE
  ─────────────────────────────────────────────────────────────────────
  .admin_suite_v4_config.json             Global app settings
  .admin_suite_v4_profiles.json           SSH profiles (no passwords)
  .admin_suite_v4_db_profiles.json        DB profiles (no passwords)
  .admin_suite_v4_snippets.json           Command snippet library
  .admin_suite_v4_recent.json             Recent connections list
  .admin_suite_v4_qhistory.json           SQL query history
  .admin_suite_v4_qfavorites.json         SQL query favorites
  .admin_suite_v4_ansible_history.json    Ansible execution history
  .admin_suite_v4_last_session.json       Last session for restore

  ~/.admin_suite_sessions/                Terminal session logs
  ~/.cache/admin_suite_xterm/             Cached xterm.js assets

  Passwords are NEVER stored in these files.
  They are stored in the OS keyring under service "Admin_Suite_v4".

================================================================================
  18. PROJECT STRUCTURE
================================================================================

linuxadmin.py                 Single-file application (~4000 lines)

Key classes:
  MainWindow                  Main application window and orchestrator
  XtermTerminalTab            SSH terminal tab (xterm.js + paramiko)
  SplitTerminalTab            Multi-pane terminal container
  LocalTerminalTab            Local bash PTY terminal
  SSHTerminalThread           SSH connection thread (paramiko)
  LocalProcessThread          Local process thread (pty)
  SFTPThread                  SFTP operations thread
  SFTPTab                     SFTP dual-pane file manager
  FileBrowserPanel            Single file browser panel (local/remote)
  RemoteEditorTab             Remote file editor tab
  RemoteSearchDialog          Remote grep search dialog
  ChmodDialog                 Permission editor dialog
  SysAdminTab                 System administration dashboard
  DatabaseManagerWidget       Database query interface
  TableDetailTab              Table schema + data detail tab
  DBWorker                    Database query execution thread
  AnsibleManagerWidget        Ansible ad-hoc + playbook center
  AnsibleRunnerThread         Ansible command execution thread
  AnsibleTestThread           SSH connectivity test thread
  ProfileDialog               SSH profile add/edit dialog
  DbProfileDialog             DB profile add/edit dialog
  ConnectionManagerDialog     Global settings dialog
  CommandPaletteDialog        Fuzzy command search dialog
  SnippetManagerDialog        Command snippet library
  KeyManagerDialog            SSH key management
  SessionLogViewerDialog      Session recording viewer
  NotificationCenterDialog    Notification history viewer
  ThemeDialog                 Theme selection dialog
  TerminalBridge              QWebChannel bridge (Python ↔ JS)
  Toast                       Desktop notification popup
  NotificationHub             Central notification dispatcher
  SQLHighlighter              SQL syntax highlighting
  SqlCompleter                SQL autocomplete
  MySQLBackend                MySQL operations
  SQLiteBackend               SQLite operations
  PGBackend                   PostgreSQL operations

Backend classes:
  MySQLBackend.connect()      → (pymysql.Connection, tunnel|None)
  MySQLBackend.schemas()      → list of database names
  MySQLBackend.tables()       → list of table names
  MySQLBackend.columns()      → list of column dicts
  MySQLBackend.run()          → (headers, rows, is_select)
  MySQLBackend.q()            → identifier quoting

  SQLiteBackend / PGBackend follow the same interface.

================================================================================
  19. TROUBLESHOOTING
================================================================================

PROBLEM: "PyQt6-WebEngine not installed"
SOLUTION: pip install PyQt6-WebEngine
          On some Linux distros, also install:
          sudo apt install libgl1-mesa-glx libegl1

PROBLEM: "Failed to load xterm.js assets"
SOLUTION: Ensure internet access on first launch.
          Delete ~/.cache/admin_suite_xterm/ and restart.

PROBLEM: Terminal shows blank/white screen
SOLUTION: Check that PyQt6-WebEngine version matches PyQt6 version.
          Try: pip install PyQt6==6.5.0 PyQt6-WebEngine==6.5.0

PROBLEM: "Backend 'postgresql' not available"
SOLUTION: pip install psycopg2-binary

PROBLEM: SSH connection fails with key
SOLUTION: Verify key path exists and permissions are 0600.
          If key is encrypted, enter passphrase in Password field.
          Try: chmod 600 ~/.ssh/id_rsa

PROBLEM: SFTP timeout on large transfers
SOLUTION: Channel timeout is set to 30s. For very slow connections,
          increase timeout in SFTPThread._connect().

PROBLEM: Local Shell tab doesn't work on Windows
SOLUTION: Local terminal requires pty/fcntl (Unix only).
          Use WSL or a remote SSH terminal instead.

PROBLEM: Ansible "not found"
SOLUTION: pip install ansible
          Ensure ansible is in PATH.

PROBLEM: Keyring errors on headless Linux
SOLUTION: Install gnome-keyring or kwallet.
          Or set: export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring

PROBLEM: VPN connect fails
SOLUTION: Verify vpn CLI path in Connection Manager.
          Ensure the VPN client is installed and the CLI is executable.
          Test manually: /opt/cisco/secureclient/bin/vpn status

PROBLEM: Session restore doesn't work
SOLUTION: Ensure profiles still exist. Deleted profiles are skipped.
          Check ~/.admin_suite_v4_last_session.json content.

PROBLEM: High DPI / blurry text
SOLUTION: The app sets AA_UseHighDpiPixmaps. For further scaling:
          export QT_SCALE_FACTOR=1.5

PROBLEM: Database tunnel fails
SOLUTION: Verify SSH credentials in the DB profile or Connection Manager.
          Ensure the remote DB port is correct.
          Check that the SSH host allows TCP forwarding.

================================================================================
  20. KNOWN LIMITATIONS
================================================================================

The following features are deliberately NOT included to keep the
application lean and focused:

  - MFA / TOTP / 2FA authentication
  - Serial console / COM port connections
  - Dynamic SOCKS proxy management
  - Oracle, MongoDB, Redis, MSSQL database backends
  - ER diagram generation
  - Inline grid editing (UPDATE via grid cells)
  - Multi-factor SSH (keyboard-interactive beyond password)
  - Windows native local terminal (requires WSL)
  - Drag-and-drop for directory trees in SFTP (files only via DnD;
    directories via context menu)
  - Ansible Vault password integration
  - Ansible roles/galaxy management


================================================================================
  21. LICENSE & DISCLAIMER
================================================================================

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

DISCLAIMER
  This tool executes commands on remote systems. Use with caution.
  Destructive database operations (TRUNCATE, DROP) require explicit
  confirmation. The authors are not responsible for any damage caused
  by misuse of this software. Always verify commands before executing
  them on production systems.

================================================================================
  END OF README
================================================================================
