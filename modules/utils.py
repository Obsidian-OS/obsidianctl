import sys
import os
import subprocess
import shlex
import re

def run_command(command, capture_output=False, text=False, check=True, input=None):
    try:
        return subprocess.run(
            shlex.split(command),
            capture_output=capture_output,
            text=text,
            check=check,
            input=input,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}", file=sys.stderr)
        print(f"Stderr: {e.stderr}", file=sys.stderr)
        print(f"Stdout: {e.stdout}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"Error: Command not found. Is '{shlex.split(command)[0]}' in your PATH?",
            file=sys.stderr,
        )
        sys.exit(1)

def get_current_slot():
    """Determines the currently booted A/B slot."""
    try:
        with open("/proc/cmdline", "r") as f:
            cmdline = f.read()
    except FileNotFoundError:
        return "unknown (/proc/cmdline not found)"
    except Exception as e:
        return f"unknown (Error reading /proc/cmdline: {e})"

    root_param = next((arg for arg in cmdline.split() if arg.startswith("root=")), None)

    if not root_param:
        return "unknown (Could not determine root from /proc/cmdline)"

    root_value = root_param.split("=", 1)[1]
    label = None

    if root_value.startswith("LABEL="):
        label = root_value.split("=", 1)[1]
    elif root_value.startswith("PARTUUID="):
        partuuid = root_value.split("=", 1)[1]
        try:
            device_path = os.path.realpath(f"/dev/disk/by-partuuid/{partuuid}")
            if not os.path.exists(device_path):
                return f"unknown (Device for PARTUUID {partuuid} not found)"
            label_output = run_command(
                f"lsblk -no LABEL {device_path}", capture_output=True, text=True
            ).stdout.strip()
            if label_output:
                label = label_output
            else:
                return f"unknown (PARTUUID {partuuid} has no label)"
        except Exception as e:
            return f"unknown (Error mapping PARTUUID to label: {e})"
    elif root_value.startswith("UUID="):
        uuid = root_value.split("=", 1)[1]
        try:
            device_path = os.path.realpath(f"/dev/disk/by-uuid/{uuid}")
            if not os.path.exists(device_path):
                return f"unknown (Device for UUID {uuid} not found)"
            label_output = run_command(
                f"lsblk -no LABEL {device_path}", capture_output=True, text=True
            ).stdout.strip()
            if label_output:
                label = label_output
            else:
                return f"unknown (UUID {uuid} has no label)"
        except Exception as e:
            return f"unknown (Error mapping UUID to label: {e})"
    else:
        return f"unknown (Unsupported root type: {root_value})"

    if label == "root_a":
        return "a"
    elif label == "root_b":
        return "b"
    else:
        return f"unknown (Label: {label})"

def _get_part_path(device, num):
    """Gets the path for a partition, handling different device name schemes."""
    dev_prefix = "p" if "nvme" in device or "mmcblk" in device else ""
    return f"{device}{dev_prefix}{num}"