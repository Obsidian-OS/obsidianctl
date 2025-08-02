def handle_switch(args):
    slot = args.slot
    print(f"Switching active boot slot to '{slot}'...")
    esp_a_path = "/dev/disk/by-label/ESP_A"
    esp_b_path = "/dev/disk/by-label/ESP_B"
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

    print(f"Active boot slot switched to '{slot}'. The change is persistent.")
    
def handle_switchonce(args):
    slot = args.slot
    print(f"Switching active boot slot to '{slot}' temporarily...")
    esp_a_path = "/dev/disk/by-label/ESP_A"
    esp_b_path = "/dev/disk/by-label/ESP_B"
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

    print(f"Active boot slot switched to '{slot}'. The change is temporarily.")
