def handle_sync(args):
    check_dependencies(
        [
            "findfs",
            "blkid",
            "rsync",
            "tune2fs",
            "sgdisk",
            "lsblk",
            "e2label",
            "fatlabel",
        ]
    )
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
        source_root_dev = lordo(source_root_label)
        target_root_dev = lordo(target_root_label)
        source_esp_dev  = lordo(source_esp_label )
        target_esp_dev  = lordo(target_esp_label )
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
    print("Copying data from source root to target root. This may take a while...")
    source_mount_point = "/mnt/obsidian_source_root"
    target_mount_point = "/mnt/obsidian_target_root"
    run_command(f"mkdir -p {source_mount_point} {target_mount_point}")
    try:
        run_command(f"mount {source_root_dev} {source_mount_point}")
        run_command(f"mount {target_root_dev} {target_mount_point}")
        run_command(f"rsync -aHAX --delete --info=progress2 {source_mount_point}/ {target_mount_point}/")
    finally:
        run_command(f"umount {source_mount_point}", check=False)
        run_command(f"umount {target_mount_point}", check=False)
        run_command(f"rmdir {source_mount_point} {target_mount_point}", check=False)
    print("Copying data from source ESP to target ESP...")
    source_esp_mount_point = "/mnt/obsidian_source_esp"
    target_esp_mount_point = "/mnt/obsidian_target_esp"
    run_command(f"mkdir -p {source_esp_mount_point} {target_esp_mount_point}")
    try:
        run_command(f"mount {source_esp_dev} {source_esp_mount_point}")
        run_command(f"mount {target_esp_dev} {target_esp_mount_point}")
        run_command(f"rsync -a --delete --info=progress2 {source_esp_mount_point}/ {target_esp_mount_point}/")
    finally:
        run_command(f"umount {source_esp_mount_point}", check=False)
        run_command(f"umount {target_esp_mount_point}", check=False)
        run_command(f"rmdir {source_esp_mount_point} {target_esp_mount_point}", check=False)
    if is_grub_active():
        print(f"Updating GRUB configuration for slot '{target_slot}'...")
        grub_mount_dir = f"/mnt/obsidian_grub_sync_{target_slot}"
        run_command(f"mkdir -p {grub_mount_dir}")
        try:
            run_command(f"mount {target_root_dev} {grub_mount_dir}")
            run_command(f"mount {target_esp_dev} {grub_mount_dir}{EFI_DIR}")
            run_command(f"mount --bind /dev {grub_mount_dir}/dev")
            run_command(f"mount --bind /proc {grub_mount_dir}/proc")
            run_command(f"mount --bind /sys {grub_mount_dir}/sys")
            run_command(f"arch-chroot {grub_mount_dir} grub-mkconfig -o {EFI_DIR}/grub/grub.cfg")
        finally:
            run_command(f"umount -R {grub_mount_dir}", check=False)
            run_command(f"rm -r {grub_mount_dir}", check=False)

    print("Sync complete.")
