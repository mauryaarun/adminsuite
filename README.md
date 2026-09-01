# Admin Suite v5 — Modular Rewrite

This is a modular rewrite of the original monolithic Admin Suite application.

## Parts

This project is being delivered in multiple parts:

- Part 1: Core scaffold, config, secrets, logging, notifications, theme, SSH credentials/host keys
- Part 2: Terminal engine
- Part 3: SFTP engine
- Part 4: Database engine
- Part 5: Ansible/sysadmin tools
- Part 6: Main window and final integration

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
