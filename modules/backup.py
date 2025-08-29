import os
import sys
import shutil
from datetime import datetime
import json
import subprocess
def handle_backup_slot(args):
    checkroot()
    slot = args.slot
    backup_dir = args.backup_dir or f"/var/backups/obsidianctl/slot_{slot}"
    full_backup = args.full_backup
    print(f"Creating backup of slot '{slot}'...")
    if full_backup:
        print("FULL backup enabled.")
    part_path = f"/dev/disk/by-label/root_{slot}"
    esp_path  = f"/dev/disk/by-label/ESP_{slot.upper()}"
    home_path =  "/dev/disk/by-label/home_ab"
    etc_path  =  "/dev/disk/by-label/etc_ab"
    var_path  =  "/dev/disk/by-label/var_ab"
    if not os.path.exists(part_path):
        print(
            f"Error: Slot '{slot}' not found. Was the system installed with obsidianctl?",
            file=sys.stderr,
        )
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"slot_{slot}_backup_{timestamp}"
    backup_path = os.path.join(backup_dir, backup_name)
    run_command(f"mkdir -p {backup_dir}")
    mount_dir = f"/mnt/obsidian_backup_{slot}"
    run_command(f"mkdir -p {mount_dir}")
    try:
        run_command(f"mount {part_path} {mount_dir}")
        if full_backup:
            run_command(f"mount {var_path}  {mount_dir}/var" )
            run_command(f"mount {etc_path}  {mount_dir}/etc" )
            run_command(f"mount {esp_path}  {mount_dir}/boot")
            run_command(f"mount {home_path} {mount_dir}/home")
        print(f"Creating backup archive at {backup_path}.sfs...")
        run_command(
            f"mksquashfs {mount_dir} {backup_path}.sfs -comp xz -noappend -wildcards -e proc/* sys/* dev/* run/* tmp/* mnt/* media/* lost+found"
        )

        metadata = {
            "slot": slot,
            "timestamp": timestamp,
            "backup_path": f"{backup_path}.sfs",
            "size": os.path.getsize(f"{backup_path}.sfs"),
            "kernel": "unknown",
            "packages": [],
            "is_full_backup": full_backup,
        }

        boot_dir = os.path.join(mount_dir, "boot")
        if os.path.exists(boot_dir):
            for f in os.listdir(boot_dir):
                if f.startswith("vmlinuz"):
                    metadata["kernel"] = f.replace("vmlinuz-", "")
                    break

        pacman_dir = os.path.join(mount_dir, "var/lib/pacman/local")
        if os.path.exists(pacman_dir):
            metadata["packages"] = [
                d
                for d in os.listdir(pacman_dir)
                if os.path.isdir(os.path.join(pacman_dir, d))
            ]

        with open(f"{backup_path}.json", "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"Backup completed successfully!")
        print(f"Archive: {backup_path}.sfs")
        print(f"Metadata: {backup_path}.json")
        print(f"Size: {metadata['size'] / (1024*1024):.1f} MB")

    finally:
        run_command(f"umount -R {mount_dir}", check=True)
        run_command(f"rm -rf {mount_dir}", check=False)


def handle_rollback_slot(args):
    checkroot()
    slot = args.slot
    backup_path = args.backup_path
    if not backup_path:
        print("Error: Please specify a backup path with --backup-path", file=sys.stderr)
        sys.exit(1)

    if not backup_path.endswith(".sfs"):
        backup_path += ".sfs"

    if not os.path.exists(backup_path):
        print(f"Error: Backup file '{backup_path}' not found.", file=sys.stderr)
        sys.stderr.write(f"Error: Backup file '{backup_path}' not found.")
        sys.exit(1)

    metadata_path = backup_path.replace(".sfs", ".json")
    is_full_backup = False
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            is_full_backup = metadata.get("is_full_backup", False)
        except json.JSONDecodeError:
            print(f"Warning: Could not read metadata from {metadata_path}. Assuming not a full backup.", file=sys.stderr)

    print(f"Rolling back slot '{slot}' from backup: {backup_path}")
    part_path = f"/dev/disk/by-label/root_{slot}"
    esp_path  = f"/dev/disk/by-label/ESP_{slot.upper()}"
    home_path =  "/dev/disk/by-label/home_ab"
    etc_path  =  "/dev/disk/by-label/etc_ab"
    var_path  =  "/dev/disk/by-label/var_ab"
    if not os.path.exists(part_path):
        print(
            f"Error: Slot '{slot}' not found. Was the system installed with obsidianctl?",
            file=sys.stderr,
        )
        sys.exit(1)

    print("WARNING: This will completely overwrite slot '{slot}' with the backup.")
    if is_full_backup:
        print("         This is a FULL system restore and will also affect ESP, home, etc, and var partitions if they exist.")
    confirm = input("Are you sure you want to proceed? (y/N): ")
    if confirm.lower() != "y":
        print("Rollback aborted.")
        sys.exit(0)

    mount_dir = f"/mnt/obsidian_rollback_{slot}"
    run_command(f"mkdir -p {mount_dir}")
    temp_extract_dir = f"/mnt/obsidian_temp_extract_{slot}"
    run_command(f"mkdir -p {temp_extract_dir}")
    try:
        print("Extracting backup to temporary location...")
        run_command(f"unsquashfs -d {temp_extract_dir} {backup_path}")
        fstype_result = subprocess.run(["blkid","-s","TYPE","-o","value",subprocess.run(["findmnt","-no","SOURCE","/"],capture_output=True,text=True).stdout.strip()],capture_output=True,text=True)
        fstype = fstype_result.stdout.strip()
        if not fstype:
            fstype = "ext4"
            print(f"Warning: Could not determine filesystem type for root partition. Defaulting to {fstype} for formatting.")

        run_command(f"umount {part_path}", check=True)
        print(f"Formatting root partition {part_path} with {fstype} and label root_{slot}...")
        run_command(f"mkfs.{fstype} -F {part_path} -L root_{slot}")
        run_command(f"mount {part_path} {mount_dir}")
        print("Copying root filesystem contents...")
        run_command(f"rsync -aAXv --exclude=/boot --exclude=/home --exclude=/etc --exclude=/var {temp_extract_dir}/ {mount_dir}/")
        if is_full_backup:
            partitions_to_restore = {
                "ESP": {"path": esp_path, "source_dir": "boot"},
                "home": {"path": home_path, "source_dir": "home"},
                "etc": {"path": etc_path, "source_dir": "etc"},
                "var": {"path": var_path, "source_dir": "var"},
            }

            for name, info in partitions_to_restore.items():
                p_path = info["path"]
                src_dir = os.path.join(temp_extract_dir, info["source_dir"])
                if os.path.exists(p_path) and os.path.isdir(src_dir):
                    print(f"Restoring {name} partition {p_path}...")
                    confirm_part = input(f"Are you sure you want to format and restore {name} partition {p_path}? (y/N): ")
                    if confirm_part.lower() == "y":
                        run_command(f"umount {p_path}", check=True)
                        part_fstype_result = subprocess.run(["blkid","-s","TYPE","-o","value",p_path],capture_output=True,text=True)
                        part_fstype = part_fstype_result.stdout.strip()
                        if not part_fstype:
                            part_fstype = "ext4"
                            print(f"Warning: Could not determine filesystem type for {p_path}. Defaulting to {part_fstype} for formatting.")

                        label_option = "-L"
                        label_value = ""
                        if name == "ESP":
                            label_value = f"ESP_{slot.upper()}"
                            if part_fstype in ["vfat", "fat"]:
                                label_option = "-n"
                            else:
                                label_option = "-L"
                        else:
                            label_value = f"{name}_ab"

                        print(f"Formatting {name} partition {p_path} with {part_fstype} and label {label_value}...")
                        run_command(f"mkfs.{part_fstype} -F {p_path} {label_option} {label_value}")

                        temp_part_mount_dir = f"/mnt/obsidian_temp_part_mount_{name}_{slot}"
                        run_command(f"mkdir -p {temp_part_mount_dir}")
                        run_command(f"mount {p_path} {temp_part_mount_dir}")
                        run_command(f"rsync -aAXv {src_dir}/ {temp_part_mount_dir}/")
                        run_command(f"umount {temp_part_mount_dir}")
                        run_command(f"rmdir {temp_part_mount_dir}")
                    else:
                        print(f"Skipping restoration of {name} partition.")
                else:
                    print(f"Skipping restoration of {name} partition: partition {p_path} not found or source directory {src_dir} missing.")

        fstab_path = os.path.join(mount_dir, "etc/fstab")
        if os.path.exists(fstab_path):
            with open(fstab_path, "r") as f:
                fstab_content = f.read()

            if slot == "a":
                fstab_content = fstab_content.replace(
                    "LABEL=root_b", "LABEL=root_a"
                ).replace("LABEL=ESP_B", "LABEL=ESP_A")
            else:
                fstab_content = fstab_content.replace(
                    "LABEL=root_a", "LABEL=root_b"
                ).replace("LABEL=ESP_A", "LABEL=ESP_B")

            with open(fstab_path, "w") as f:
                f.write(fstab_content)

        print(f"Rollback completed successfully!")
    finally:
        run_command(f"umount -R {mount_dir}", check=True)
        run_command(f"rmdir {mount_dir}", check=False)
        run_command(f"rm -rf {temp_extract_dir}", check=False)

