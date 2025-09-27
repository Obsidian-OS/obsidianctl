def handle_update_mkobsidiansfs(args):
    if shutil.which("mkobsidiansfs"):
        os.system(f"mkobsidiansfs {args.system_sfs} system.sfs")
    else:
        if shutil.which("git"):
            os.system(
                f"git clone https://github.com/Obsidian-OS/mkobsidiansfs/ /tmp/mkobsidiansfs;chmod u+x /tmp/mkobsidiansfs/mkobsidiansfs;/tmp/mkobsidiansfs/mkobsidiansfs {args.system_sfs} tmp_system.sfs"
            )
        else:
            print(
                "No git or mkobsidiansfs found. Please install one of these to directly pass in an .mkobsfs."
            )
            sys.exit(1)
    args.system_sfs = "system.sfs"
    handle_update(args)
    os.remove("system.sfs")


def handle_update(args):
    checkroot()
    fstype = subprocess.run(
        [
            "blkid",
            "-s",
            "TYPE",
            "-o",
            "value",
            subprocess.run(
                ["findmnt", "-no", "SOURCE", "/"], capture_output=True, text=True
            ).stdout.strip(),
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    slot = args.slot
    system_sfs = args.system_sfs
    if not os.path.exists(system_sfs):
        print(f"Error: System image '{system_sfs}' not found.", file=sys.stderr)
        sys.exit(1)
    _, ext = os.path.splitext(system_sfs)
    if ext == ".mkobsfs":
        handle_update_mkobsidiansfs(args)
        sys.exit()
    target_label = f"root_{slot}"
    esp_label = f"ESP_{slot.upper()}"
    print(f"Updating slot '{slot}' with image '{system_sfs}'...")
    print(f"WARNING: THIS WILL ERASE ALL OF SLOT {slot.upper()}. INCLUDING /root.")
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != "y":
        print("Operation Canceled.")
        exit(1)
    print("Formatting partition...")
    run_command(f"mkfs.{fstype} -F -L {target_label} /dev/disk/by-label/{target_label}")
    mount_dir = f"/mnt/obsidian_update_{slot}"
    run_command(f"mkdir -p {mount_dir}")
    try:
        print(f"Mounting partition for slot '{slot}'...")
        run_command(f"mount /dev/disk/by-label/{target_label} {mount_dir}")
        print(f"Extracting system from {system_sfs} to slot '{slot}'...")
        run_command(f"unsquashfs -f -d {mount_dir} -no-xattrs {system_sfs}")
        print(f"Generating fstab for slot '{slot}'...")
        fstab_content = f"""
LABEL={target_label}  /      {fstype}  defaults,noatime 0 1
LABEL={esp_label}     /boot  vfat  defaults,noatime 0 2
LABEL=etc_ab  /etc   {fstype}  defaults,noatime 0 2
LABEL=var_ab  /var   {fstype}  defaults,noatime 0 2
LABEL=home_ab /home  {fstype}  defaults,noatime 0 2
"""
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

        bootloader = detect_bootloader()
        if bootloader == 'grub':
            print("Regenerating GRUB configuration...")
            mount_dir_grub = f"/mnt/obsidian_grub_{slot}"
            run_command(f"mkdir -p {mount_dir_grub}")
            try:
                run_command(f"mount /dev/disk/by-label/root_{slot} {mount_dir_grub}")
                run_command(f"mount /dev/disk/by-label/ESP_{slot.upper()} {mount_dir_grub}/boot")
                run_command(f"mount /dev/disk/by-label/etc_ab {mount_dir_grub}/etc")
                run_command(f"mount /dev/disk/by-label/var_ab {mount_dir_grub}/var")
                run_command(f"mount /dev/disk/by-label/home_ab {mount_dir_grub}/home")
                grub_cmd = get_grub_command()
                if grub_cmd:
                    run_command(f"arch-chroot {mount_dir_grub} {grub_cmd} -o /boot/grub/grub.cfg")
                else:
                    print("Warning: No GRUB command found. Skipping regeneration.", file=sys.stderr)
            finally:
                run_command(f"umount -R {mount_dir_grub}", check=False)
                run_command(f"rm -r {mount_dir_grub}", check=False)
        elif bootloader == 'systemd-boot':
            print("Updating systemd-boot configuration...")
            esp_config_mount = f"/mnt/obsidian_esp_config_{slot}"
            run_command(f"mkdir -p {esp_config_mount}")
            try:
                run_command(f"mount /dev/disk/by-label/ESP_{slot.upper()} {esp_config_mount}")
                root_partuuid = run_command(
                    f"blkid -s PARTUUID -o value /dev/disk/by-label/root_{slot}", capture_output=True, text=True
                ).stdout.strip()
                if not root_partuuid:
                    print(f"Could not determine PARTUUID for root_{slot}. Skipping boot config.", file=sys.stderr)
                else:
                    run_command(f"mkdir -p {esp_config_mount}/loader/entries")
                    loader_conf = "timeout 0\ndefault obsidian-a.conf\n"
                    entry_conf = f"""title ObsidianOS (Slot {slot.upper()})
linux /vmlinuz-linux
initrd /initramfs-linux.img
options root=PARTUUID={root_partuuid} rw
"""
                    with open(f"{esp_config_mount}/loader/loader.conf", "w") as f:
                        f.write(loader_conf)
                    with open(f"{esp_config_mount}/loader/entries/obsidian-{slot}.conf", "w") as f:
                        f.write(entry_conf)
            finally:
                run_command(f"umount {esp_config_mount}", check=False)
                run_command(f"rm -r {esp_config_mount}", check=False)

    finally:
        print("Unmounting partition...")
        run_command(f"umount -R {mount_dir}", check=False)
        run_command(f"rm -r {mount_dir}", check=False)

    print(f"Update for slot '{slot}' complete!")
    print("You may need to switch to this slot and reboot to use the updated system.")
    if args.switch:
        print(f"Switching the active slot to {slot.upper()}")
        run_command(f"obsidianctl switch {slot}", check=False)
