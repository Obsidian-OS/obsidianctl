
def handle_update(args):
    slot = args.slot
    system_sfs = args.system_sfs
    if not os.path.exists(system_sfs):
        print(f"Error: System image '{system_sfs}' not found.", file=sys.stderr)
        sys.exit(1)

    target_label = f"root_{slot}"
    print(f"Updating slot '{slot}' with image '{system_sfs}'...")
    print(f"WARNING: THIS WILL ERASE ALL OF SLOT {slot.upper()}. INCLUDING /root.")
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != "y":
        print("Operation Canceled.")
        exit(1)
    print("Formatting partition...")
    run_command(f"mkfs.ext4 -F -L {target_label} /dev/disk/by-label/{target_label}")
    mount_dir = f"/mnt/obsidian_update_{slot}"
    run_command(f"mkdir -p {mount_dir}")
    try:
        print(f"Mounting partition for slot '{slot}'...")
        run_command(f"mount /dev/disk/by-label/{target_label} {mount_dir}")
        print(f"Extracting system from {system_sfs} to slot '{slot}'...")
        run_command(f"unsquashfs -f -d {mount_dir} -no-xattrs {system_sfs}")
        print(f"Generating fstab for slot '{slot}'...")
        fstab_content = f'''
fstab_content = f'''
LABEL={target_label}  /      ext4  defaults,noatime 0 1
LABEL={esp_label}     /boot  vfat  defaults,noatime 0 2
LABEL=etc_ab  /etc   ext4  defaults,noatime 0 2
LABEL=var_ab  /var   ext4  defaults,noatime 0 2
LABEL=home_ab /home  ext4  defaults,noatime 0 2
'''
'''
        fstab_path = f"{mount_dir}/etc/fstab"
        if not os.path.exists(os.path.dirname(fstab_path)):
            run_command(f"mkdir -p {os.path.dirname(fstab_path)}")

        with open(fstab_path, "w") as f:
            f.write(fstab_content.strip())
        print(f"Copying support files to slot '{slot}'...")
        script_path = os.path.realpath(sys.argv[0])
        obsidianctl_dest = f"{mount_dir}/usr/bin/obsidianctl"
        run_command(f"mkdir -p {mount_dir}/usr/bin")
        run_command(f"cp {script_path} {obsidianctl_dest}")
        run_command(f"chmod +x {obsidianctl_dest}")
        run_command(f"cp /etc/os-release {mount_dir}/etc/os-release")

        print(f"Populating ESP_{slot.upper()} with new boot files...")
        esp_tmp_mount = "/mnt/obsidian_esp_tmp"
        run_command(f"mkdir -p {esp_tmp_mount}")
        try:
            run_command(f"mount /dev/disk/by-label/ESP_{slot.upper()} {esp_tmp_mount}")
            run_command(f"rsync -aK --delete {mount_dir}/boot/ {esp_tmp_mount}/")
        finally:
            run_command(f"umount {esp_tmp_mount}", check=False)
            run_command(f"rmdir {esp_tmp_mount}", check=False)

    finally:
        print("Unmounting partition...")
        run_command(f"umount -R {mount_dir}", check=False)
        run_command(f"rm -r {mount_dir}", check=False)

    print(f"Update for slot '{slot}' complete!")
    print("You may need to switch to this slot and reboot to use the updated system.")