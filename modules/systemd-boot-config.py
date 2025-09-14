def handle_switch_kernel(args):
    checkroot()
    kernel_name = args.kernel_name
    target_device = args.device if args.device else get_primary_disk_device()
    target_slot = args.slot

    esp_labels_to_check = {}
    if target_slot == 'a':
        esp_labels_to_check['ESP_A'] = None
    elif target_slot == 'b':
        esp_labels_to_check['ESP_B'] = None
    else:
        esp_labels_to_check['ESP_A'] = None
        esp_labels_to_check['ESP_B'] = None

    esp_paths = {}
    for label in esp_labels_to_check.keys():
        path = lordo(label, target_device)
        if not path:
            print(f"Error: Could not find partition with label '{label}' on {target_device}.", file=sys.stderr)
            sys.exit(1)
        esp_paths[label] = path

    temp_mount_dirs = {}
    try:
        for label, part_path in esp_paths.items():
            temp_mount_dir = tempfile.mkdtemp()
            temp_mount_dirs[label] = temp_mount_dir
            run_command(f"mount {part_path} {temp_mount_dir}")

            kernel_entry_path = os.path.join(temp_mount_dir, "loader/entries", f"obsidian-{kernel_name}.conf")
            if not os.path.exists(kernel_entry_path):
                print(f"Error: Kernel entry 'obsidian-{kernel_name}.conf' not found in {temp_mount_dir}.", file=sys.stderr)
                sys.exit(1)

        print(f"Switching default kernel to 'obsidian-{kernel_name}.conf'...")

        for label, mount_dir in temp_mount_dirs.items():
            loader_conf_path = os.path.join(mount_dir, "loader/loader.conf")
            if not os.path.exists(loader_conf_path):
                print(f"Warning: loader.conf not found in {mount_dir}. Skipping.", file=sys.stderr)
                continue

            with open(loader_conf_path, "r") as f:
                lines = f.readlines()

            new_lines = []
            found_default = False
            for line in lines:
                if line.strip().startswith("default"):
                    new_lines.append(f"default obsidian-{kernel_name}.conf\n")
                    found_default = True
                else:
                    new_lines.append(line)

            if not found_default:
                new_lines.append(f"default obsidian-{kernel_name}.conf\n")

            with open(loader_conf_path, "w") as f:
                f.writelines(new_lines)
            print(f"Updated loader.conf in {mount_dir}")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        for label, mount_dir in temp_mount_dirs.items():
            if os.path.ismount(mount_dir):
                run_command(f"umount {mount_dir}", check=False)
            run_command(f"rmdir {mount_dir}", check=False)

    print("Kernel switch complete. Reboot to apply changes.")
