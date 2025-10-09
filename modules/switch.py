def handle_switch(args):
    checkroot()
    slot = args.slot
    print(f"Switching active boot slot to '{slot}'...")
    esp_a_path = lordo("ESP_A")
    esp_b_path = lordo("ESP_B")
    if not os.path.exists(esp_a_path) or not os.path.exists(esp_b_path):
        print(
            "ESP partitions not found. Was the system installed with obsidianctl?",
            file=sys.stderr,
        )
        sys.exit(1)

    if is_systemd_boot():
        esp_a_path = lordo("ESP_A")
        esp_b_path = lordo("ESP_B")
        if not os.path.exists(esp_a_path) or not os.path.exists(esp_b_path):
            print(
                "ESP partitions not found. Was the system installed with obsidianctl?",
                file=sys.stderr,
            )
            sys.exit(1)

        esp_mount_dir = "/mnt/obsidian_esp_tmp"
        run_command(f"mkdir -p {esp_mount_dir}")
        try:
            run_command(f"mount {esp_a_path} {esp_mount_dir}")
            run_command(
                f"bootctl --esp-path={esp_mount_dir} set-default obsidian-{slot}.conf"
            )
            print(f"Default boot entry set to obsidian-{slot}.conf on ESP_A.")
        finally:
            run_command(f"umount {esp_mount_dir}", check=False)

        try:
            run_command(f"mount {esp_b_path} {esp_mount_dir}")
            run_command(
                f"bootctl --esp-path={esp_mount_dir} set-default obsidian-{slot}.conf"
            )
            print(f"Default boot entry set to obsidian-{slot}.conf on ESP_B.")
        finally:
            run_command(f"umount {esp_mount_dir}", check=False)
            run_command(f"rm -r {esp_mount_dir}", check=False)
    elif is_grub_active():
        grub_entry = f"ObsidianOS (Slot {slot.upper()})"
        try:
            run_command(f"grub-set-default \"{grub_entry}\"")
            print(f"Default GRUB boot entry set to '{grub_entry}'.")
        except Exception as e:
            print(f"Error setting GRUB default entry: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Neither systemd-boot nor GRUB detected as active bootloader.", file=sys.stderr)
        sys.exit(1)
    
def handle_switchonce(args):
    checkroot()
    slot = args.slot
    print(f"Switching active boot slot to '{slot}' temporarily...")
    esp_a_path = lordo("ESP_A")
    esp_b_path = lordo("ESP_B")
    if not os.path.exists(esp_a_path) or not os.path.exists(esp_b_path):
        print(
            "ESP partitions not found. Was the system installed with obsidianctl?",
            file=sys.stderr,
        )
        sys.exit(1)

    if is_systemd_boot():
        esp_a_path = lordo("ESP_A")
        esp_b_path = lordo("ESP_B")
        if not os.path.exists(esp_a_path) or not os.path.exists(esp_b_path):
            print(
                "ESP partitions not found. Was the system installed with obsidianctl?",
                file=sys.stderr,
            )
            sys.exit(1)

        esp_mount_dir = "/mnt/obsidian_esp_tmp"
        run_command(f"mkdir -p {esp_mount_dir}")
        try:
            run_command(f"mount {esp_a_path} {esp_mount_dir}")
            run_command(
                f"bootctl --esp-path={esp_mount_dir} set-oneshot obsidian-{slot}.conf"
            )
            print(f"Default boot entry set to obsidian-{slot}.conf on ESP_A.")
        finally:
            run_command(f"umount {esp_mount_dir}", check=False)

        try:
            run_command(f"mount {esp_b_path} {esp_mount_dir}")
            run_command(
                f"bootctl --esp-path={esp_mount_dir} set-oneshot obsidian-{slot}.conf"
            )
            print(f"Default boot entry set to obsidian-{slot}.conf on ESP_B.")
        finally:
            run_command(f"umount {esp_mount_dir}", check=False)
            run_command(f"rm -r {esp_mount_dir}", check=False)
    elif is_grub_active():
        grub_entry = f"ObsidianOS (Slot {slot.upper()})"
        try:
            run_command(f"grub-reboot \"{grub_entry}\"")
            print(f"GRUB boot entry for next reboot set to '{grub_entry}'.")
        except Exception as e:
            print(f"Error setting GRUB reboot entry: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Neither systemd-boot nor GRUB detected as active bootloader.", file=sys.stderr)
        sys.exit(1)
