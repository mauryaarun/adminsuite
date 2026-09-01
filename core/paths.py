"""
Central filesystem paths for Admin Suite.
"""

from pathlib import Path

HOME = Path.home()

APP_NAME = "Admin_Suite_v5"

# Main JSON state files.
CONFIG_FILE = HOME / ".admin_suite_v5_config.json"
PROFILES_FILE = HOME / ".admin_suite_v5_profiles.json"
DB_PROFILES_FILE = HOME / ".admin_suite_v5_db_profiles.json"
SNIPPETS_FILE = HOME / ".admin_suite_v5_snippets.json"
RECENT_FILE = HOME / ".admin_suite_v5_recent.json"

# Database query history/favorites.
QUERY_HISTORY_FILE = HOME / ".admin_suite_v5_query_history.json"
QUERY_FAVORITES_FILE = HOME / ".admin_suite_v5_query_favorites.json"

# Ansible/multi-host history and command sets.
ANSIBLE_HISTORY_FILE = HOME / ".admin_suite_v5_ansible_history.json"
ANSIBLE_COMMAND_SETS_FILE = HOME / ".admin_suite_v5_ansible_command_sets.json"

# Session restore.
LAST_SESSION_FILE = HOME / ".admin_suite_v5_last_session.json"

# Terminal session logs.
LOG_DIR = HOME / ".admin_suite_sessions"

# xterm.js assets.
XTERM_DIR = HOME / ".cache" / "admin_suite_xterm"

# SSH known hosts used by Admin Suite trust-on-first-use policy.
HOST_KEYS_FILE = HOME / ".admin_suite_v5_known_hosts"


def ensure_dirs() -> None:
    """
    Create required directories if they do not exist.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    XTERM_DIR.mkdir(parents=True, exist_ok=True)
