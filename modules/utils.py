import shutil
import shlex
import sys
import os
import subprocess
import re

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


def get_current_slot():
    try:
        findmnt_output = subprocess.check_output(
            ["findmnt", "-n", "-o", "SOURCE,UUID,PARTUUID,LABEL,PARTLABEL", "/"],
            text=True,
        ).strip()
        for item in findmnt_output.split():
            if "_a" in item:
                return "a"
            elif "_b" in item:
                return "b"

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return "unknown"
