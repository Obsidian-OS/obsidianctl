import os
import sys
import shutil
import tarfile
from datetime import datetime


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

        import json

        with open(f"{backup_path}.json", "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"Backup completed successfully!")
        print(f"Archive: {backup_path}.tar.gz")
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
        sys.exit(1)

    print(f"Rolling back slot '{slot}' from backup: {backup_path}")
    part_path = f"/dev/disk/by-label/root_{slot}"
    if not os.path.exists(part_path):
        print(
            f"Error: Slot '{slot}' not found. Was the system installed with obsidianctl?",
            file=sys.stderr,
        )
        sys.exit(1)

    print("WARNING: This will completely overwrite slot '{slot}' with the backup.")
    confirm = input("Are you sure you want to proceed? (y/N): ")
    if confirm.lower() != "y":
        print("Rollback aborted.")
        sys.exit(0)

    mount_dir = f"/mnt/obsidian_rollback_{slot}"
    run_command(f"mkdir -p {mount_dir}")
    try:
        fstype=subprocess.run(["blkid","-s","TYPE","-o","value",subprocess.run(["findmnt","-no","SOURCE","/"],capture_output=True,text=True).stdout.strip()],capture_output=True,text=True).stdout.strip()
        run_command(f"umount {part_path}", check=False)
        print(f"Formatting partition {part_path}...")
        run_command(f"mkfs.{fstype} -F {part_path}")
        run_command(f"mount {part_path} {mount_dir}")
        print("Extracting backup...")
        run_command(f"unsquashfs -d {mount_dir} {backup_path}")
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
        run_command(f"umount {mount_dir}", check=False)
        run_command(f"rmdir {mount_dir}", check=False)

