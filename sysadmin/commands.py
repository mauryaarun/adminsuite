"""
SysAdmin dashboard command definitions.
"""
SYSADMIN_SECTIONS = [
    "Overview",
    "Users",
    "Services",
    "Processes",
    "Storage",
    "Network",
    "Journal",
    "Cron",
]

SYSADMIN_CMDS = {
    "Overview": (
        "echo '== HOSTNAME =='; hostnamectl 2>/dev/null || hostname; "
        "echo; echo '== KERNEL =='; uname -a; "
        "echo; echo '== UPTIME/LOAD =='; uptime; "
        "echo; echo '== MEMORY =='; free -h; "
        "echo; echo '== CPU =='; lscpu 2>/dev/null | head -16; "
        "echo; echo '== SENSORS =='; sensors 2>/dev/null | head -20 "
        "|| echo 'lm-sensors not available' "
    ),
    "Users": "cat /etc/passwd",
    "Services": (
        "systemctl list-units --type=service --all --no-legend --plain 2>/dev/null "
        "|| service --status-all 2>/dev/null "
    ),
    "Processes": "ps aux --sort=-%cpu | head -120",
    "Storage": (
        "echo '== LSBLK =='; lsblk 2>/dev/null; "
        "echo; echo '== DF =='; df -hT; "
        "echo; echo '== SWAP =='; swapon --show 2>/dev/null; "
        "echo; echo '== LVM =='; sudo -n vgs 2>/dev/null; sudo -n lvs 2>/dev/null; "
        "echo; echo '== NFS MOUNTS =='; mount | grep -E 'nfs|cifs' || echo none "
    ),
    "Network": (
        "echo '== INTERFACES =='; ip -brief addr 2>/dev/null || ifconfig -a; "
        "echo; echo '== ROUTES =='; ip route 2>/dev/null; "
        "echo; echo '== LISTENING =='; ss -tunlp 2>/dev/null | head -40; "
        "echo; echo '== DNS =='; cat /etc/resolv.conf; "
        "echo; echo '== FIREWALL =='; sudo -n ufw status 2>/dev/null "
        "|| sudo -n firewall-cmd --list-all 2>/dev/null "
        "|| sudo -n iptables -L -n 2>/dev/null | head -30 "
        "|| echo 'no firewall tool / no permission' "
    ),
    "Journal": (
        "journalctl -n 200 --no-pager 2>/dev/null "
        "|| tail -n 200 /var/log/syslog 2>/dev/null "
        "|| tail -n 200 /var/log/messages 2>/dev/null "
        "|| echo 'no journal access' "
    ),
    "Cron": (
        "echo '== SYSTEM CRONTAB =='; cat /etc/crontab 2>/dev/null; "
        "echo; echo '== CRON.D =='; for f in /etc/cron.d/*; do "
        "echo \"--- $f\"; cat \"$f\" 2>/dev/null; done; "
        "echo; echo '== USER CRONTAB =='; crontab -l 2>/dev/null "
        "|| echo 'no user crontab' "
    ),
}