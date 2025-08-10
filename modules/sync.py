def handle_sync(args):
    checkroot()
    target_slot = args.slot
    current_slot = get_current_slot()
    if target_slot == current_slot:
        print(f"Cannot sync slot {current_slot} to itself.")
        sys.exit(1)

    print(f"Current slot: {current_slot}")
    print(f"Target slot: {target_slot}")
    source_root_label = f"ROOT_{current_slot.upper()}"
    target_root_label = f"ROOT_{target_slot.upper()}"
    try:
        source_root_dev = run_command(
            f"findfs PARTLABEL={source_root_label}", capture_output=True
        ).stdout.strip()
        target_root_dev = run_command(
            f"findfs PARTLABEL={target_root_label}", capture_output=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(
            "Error: Could not find source or target root partitions by label.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not source_root_dev or not target_root_dev:
        print(
            "Error: Could not find source or target root partitions by label.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Source root device: {source_root_dev}")
    print(f"Target root device: {target_root_dev}")
    print(
        f"Syncing root partition from {source_root_dev} to {target_root_dev} using dd..."
    )
    run_command(f"dd if={source_root_dev} of={target_root_dev} bs=4M status=progress")
    print("Updating partition UUID (PARTUUID)...")
    target_disk = run_command(
        f"lsblk -no pkname {target_root_dev}", capture_output=True
    ).stdout.strip()
    partition_number = "".join(filter(str.isdigit, target_root_dev.split("/")[-1]))
    run_command(f"sgdisk --partition-guid={partition_number}:R /dev/{target_disk}")
    print("Updating filesystem UUID...")
    run_command(f"tune2fs -U random {target_root_dev}")
    print("Syncing ESP Partitions...")
    source_esp_label = f"ESP_{current_slot.upper()}"
    target_esp_label = f"ESP_{target_slot.upper()}"
    try:
        source_esp_dev = run_command(
            f"findfs PARTLABEL={source_esp_label}", capture_output=True
        ).stdout.strip()
        target_esp_dev = run_command(
            f"findfs PARTLABEL={target_esp_label}", capture_output=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(
            "Error: Could not find source or target ESP partitions by label.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not source_esp_dev or not target_esp_dev:
        print(
            "Error: Could not find source or target ESP partitions by label.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Source ESP device: {source_esp_dev}")
    print(f"Target ESP device: {target_esp_dev}")
    print(
        f"Syncing ESP partition from {source_esp_dev} to {target_esp_dev} using dd..."
    )
    run_command(f"dd if={source_esp_dev} of={target_esp_dev} bs=1M status=progress")
    print("Updating ESP partition UUID (PARTUUID)...")
    target_esp_disk = run_command(
        f"lsblk -no pkname {target_esp_dev}", capture_output=True
    ).stdout.strip()
    esp_partition_number = "".join(filter(str.isdigit, target_esp_dev.split("/")[-1]))
    run_command(
        f"sgdisk --partition-guid={esp_partition_number}:R /dev/{target_esp_disk}"
    )
    print("Sync complete.")
