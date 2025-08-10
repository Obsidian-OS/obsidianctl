import sys
import subprocess
from .utils import check_dependencies, check_root, get_current_slot, run_command

def handle_sync(args):
    check_dependencies(["findfs", "blkid", "dd", "tune2fs", "sgdisk", "lsblk", "e2label", "fatlabel"])
    checkroot()
    target_slot = args.slot
    current_slot = get_current_slot()
    if target_slot == current_slot:
        print(f"Error: Cannot sync slot {current_slot} to itself.", file=sys.stderr)
        sys.exit(1)

    print(f"Current slot: {current_slot}")
    print(f"Target slot: {target_slot}")
    source_root_label = f"root_{current_slot.lower()}"
    target_root_label = f"root_{target_slot.lower()}"
    source_esp_label = f"ESP_{current_slot.upper()}"
    target_esp_label = f"ESP_{target_slot.upper()}"
    try:
        source_root_dev = run_command(
            f"findfs LABEL={source_root_label}", capture_output=True
        ).stdout.strip()
        target_root_dev = run_command(
            f"findfs LABEL={target_root_label}", capture_output=True
        ).stdout.strip()
        source_esp_dev = run_command(
            f"findfs LABEL={source_esp_label}", capture_output=True
        ).stdout.strip()
        target_esp_dev = run_command(
            f"findfs LABEL={target_esp_label}", capture_output=True
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: Could not find partitions by label. {e}", file=sys.stderr)
        sys.exit(1)

    if not all([source_root_dev, target_root_dev, source_esp_dev, target_esp_dev]):
        print(
            "Error: Could not find one or more source or target partitions by label.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Source root device: {source_root_dev}")
    print(f"Target root device: {target_root_dev}")
    print(f"Source ESP device: {source_esp_dev}")
    print(f"Target ESP device: {target_esp_dev}")
    print("Reading original partition identifiers from target slot...")
    try:
        target_root_fs_uuid = run_command(
            f"blkid -s UUID -o value {target_root_dev}", capture_output=True
        ).stdout.strip()
        target_root_part_uuid = run_command(
            f"blkid -s PARTUUID -o value {target_root_dev}", capture_output=True
        ).stdout.strip()
        target_esp_part_uuid = run_command(
            f"blkid -s PARTUUID -o value {target_esp_dev}", capture_output=True
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: Could not read partition identifiers. {e}", file=sys.stderr)
        sys.exit(1)
    if not all([target_root_fs_uuid, target_root_part_uuid, target_esp_part_uuid]):
        print(
            "Error: Could not read one or more original partition identifiers from the target slot.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Copying data from source root to target root. This may take a while...")
    run_command(f"dd if={source_root_dev} of={target_root_dev} bs=4M status=progress")
    print(f"Setting label of {target_root_dev} to {target_root_label}")
    run_command(f"e2label {target_root_dev} {target_root_label}")
    print("Restoring original filesystem identifier for the root partition...")
    run_command(f"tune2fs -U {target_root_fs_uuid} {target_root_dev}")
    print("Restoring original partition identifier for the root partition...")
    target_disk = run_command(
        f"lsblk -no pkname {target_root_dev}", capture_output=True
    ).stdout.strip()
    partition_number = "".join(filter(str.isdigit, target_root_dev.split("/")[-1]))
    run_command(
        f"sgdisk --partition-guid={partition_number}:{target_root_part_uuid} /dev/{target_disk}"
    )
    print("Copying data from source ESP to target ESP...")
    run_command(f"dd if={source_esp_dev} of={target_esp_dev} bs=1M status=progress")
    print(f"Setting label of {target_esp_dev} to {target_esp_label}")
    run_command(f"fatlabel {target_esp_dev} {target_esp_label}")
    print("Restoring original partition identifier for the ESP...")
    target_esp_disk = run_command(
        f"lsblk -no pkname {target_esp_dev}", capture_output=True
    ).stdout.strip()
    esp_partition_number = "".join(filter(str.isdigit, target_esp_dev.split("/")[-1]))
    run_command(
        f"sgdisk --partition-guid={esp_partition_number}:{target_esp_part_uuid} /dev/{target_esp_disk}"
    )
    print("Sync complete.")