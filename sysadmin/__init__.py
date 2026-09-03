"""
SysAdmin dashboard.
"""
from admin_suite.sysadmin.commands import (
    SYSADMIN_SECTIONS,
    SYSADMIN_CMDS,
)
from admin_suite.sysadmin.dashboard import (
    SysAdminTab,
)

__all__ = [
    "SYSADMIN_SECTIONS",
    "SYSADMIN_CMDS",
    "SysAdminTab",
]