#!/usr/bin/env python3
import argparse
import shutil
import shlex
import sys
import os
import subprocess
import re
import pwd
import tempfile

if os.path.exists("/efi"):
    EFI_DIR = "/efi"
else:
    EFI_DIR = "/boot"

MIGRATION_LOG_FILE = "/etc/obsidianctl/migrations/applied.log"


def get_applied_migrations():
    if not os.path.exists(MIGRATION_LOG_FILE):
        return []
    with open(MIGRATION_LOG_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def record_applied_migration(migration_id):
    os.makedirs(os.path.dirname(MIGRATION_LOG_FILE), exist_ok=True)
    with open(MIGRATION_LOG_FILE, "a") as f:
        f.write(f"{migration_id}\n")


def remove_applied_migration(migration_id):
    if not os.path.exists(MIGRATION_LOG_FILE):
        return
    migrations = get_applied_migrations()
    with open(MIGRATION_LOG_FILE, "w") as f:
        for mid in migrations:
            if mid != str(migration_id):
                f.write(f"{mid}\n")


def is_grub_available():
    return (
        shutil.which("grub-install") is not None
        or shutil.which("grub2-install") is not None
    )


def is_grub_active():
    if os.path.exists(f"{EFI_DIR}/grub/grub.cfg"):
        return True
    try:
        efibootmgr_output = subprocess.check_output(["efibootmgr", "-v"], text=True)
        if "grub" in efibootmgr_output.lower():
            return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return False


def is_systemd_boot():
    try:
        output = subprocess.check_output(
            ["bootctl", "status"], stderr=subprocess.DEVNULL, text=True
        )
        if "systemd-boot" in output or "Boot Loader:" in output:
            return True
        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def lordo(
    label, disk=None
):  # LORDO = LABEL On Root Disk Only, returns /dev/disk/by-uuid/UUID
    root_part = subprocess.check_output(
        ["findmnt", "-no", "SOURCE", "/"], text=True
    ).strip()
    if disk is None:
        disk_name = subprocess.check_output(
            ["lsblk", "-no", "PKNAME", root_part], text=True
        ).strip()
        disk = f"/dev/{disk_name}"
    parts = subprocess.check_output(
        ["lsblk", "-o", "NAME,LABEL,UUID", "-l", disk], text=True
    ).splitlines()
    for p in parts:
        fields = p.split(None, 2)  # NAME, LABEL, UUID
        if len(fields) < 3:
            continue
        name, lbl, uuid = fields
        if lbl.strip() == label:
            return f"/dev/disk/by-uuid/{uuid}"

    return None


def check_dependencies(commands):
    commands.extend(["curl", "tar", "mksquashfs", "unsquashfs"])
    for command in commands:
        if not shutil.which(command):
            print(f"Error: Required command '{command}' not found.", file=sys.stderr)
            sys.exit(1)


def checkroot():
    if os.geteuid() != 0:
        print("This script must be run as root.", file=sys.stderr)
        sys.exit(1)


def run_command(command, **kwargs):
    kwargs.setdefault("text", True)
    check = kwargs.pop("check", True)
    try:
        process = subprocess.run(
            command if isinstance(command, list) else shlex.split(command),
            check=check,
            **kwargs,
        )
        return process
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}", file=sys.stderr)
        print(f"Exit Code: {e.returncode}", file=sys.stderr)
        if e.stdout:
            print(f"Stdout: {e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"Stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Command not found for: {command}", file=sys.stderr)
        sys.exit(1)


def _get_part_path(device, part_num):
    if "nvme" in device:
        return f"{device}p{part_num}"
    else:
        return f"{device}{part_num}"


def get_current_slot_systemd():
    try:
        bootctl_output = subprocess.check_output(["bootctl", "status"], text=True)
        match = re.search(
            r"^\s*id:\s+.*obsidian-([ab])\.conf", bootctl_output, re.MULTILINE
        )
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return "unknown"


# def get_current_slot():
#    if is_systemd_boot():
#        return get_current_slot_systemd()
#    elif is_grub_active():
#        try:
#            with open("/proc/cmdline", "r") as f:
#                cmdline = f.read()
#            root_match = re.search(r"root=(PARTUUID=)?([a-f0-9\-]+|/dev/[^\s]+)", cmdline)
#            if root_match:
#                root_identifier = root_match.group(2)
#                if "PARTUUID" in root_match.group(0):
#                    # If it's a PARTUUID, find the device path first
#                    device_path_output = subprocess.check_output(["blkid", "-t", f"PARTUUID={root_identifier}", "-o", "device"], text=True).strip()
#                    if device_path_output:
#                        root_device = device_path_output
#                    else:
#                        return "unknown"
#                else:
#                    root_device = root_identifier
#
#                # Get the label of the root device
#                label_output = subprocess.check_output(["lsblk", "-no", "LABEL", root_device], text=True).strip()
#                if "root_a" in label_output:
#                    return "a"
#                elif "root_b" in label_output:
#                    return "b"
#        except (subprocess.CalledProcessError, FileNotFoundError):
#            pass
#    return "unknown"
def get_current_slot():
    try:
        result = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE,UUID,PARTUUID,LABEL,PARTLABEL", "/"],
            capture_output=True,
            text=True,
            check=True,
        )
        for item in result.stdout.split():
            if "_a" in item:
                return "a"
            elif "_b" in item:
                return "b"
    except subprocess.CalledProcessError:
        pass
    return "unknown"


def handle_currentslot(ignoreitman):
    print(get_current_slot())


def get_user_home_dir():
    if "SUDO_USER" in os.environ:
        try:
            user = os.environ["SUDO_USER"]
            return pwd.getpwnam(user).pw_dir
        except KeyError:
            pass
    return os.path.expanduser("~")


def get_primary_disk_device():
    root_part = run_command("findmnt -no SOURCE /", capture_output=True).stdout.strip()
    disk_name = run_command(
        f"lsblk -no PKNAME {root_part}", capture_output=True
    ).stdout.strip()
    return f"/dev/{disk_name}"
