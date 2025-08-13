def handle_dual_boot(args):
    checkroot()
    device = args.device
    system_sfs = args.system_sfs

    if not os.path.exists(device):
        print(f"Error: Device '{device}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(system_sfs):
        print(f"Error: System image '{system_sfs}' not found.", file=sys.stderr)
        sys.exit(1)

    print(
        f"WARNING: This will install ObsidianOS on {device} alongside your existing OS."
    )
    print("Please ensure you have enough free space on the device.")
    confirm = input("Are you sure you want to proceed? (y/N): ")
    if confirm.lower() != "y":
        print("Installation aborted.")
        sys.exit(0)

    print("Partitioning device...")
    partition_table = f"""
label: gpt
,{args.esp_size},U,*
,{args.esp_size},U,*
,{args.rootfs_size},L,*
,{args.rootfs_size},L,*
,{args.etc_size},L,*
,{args.var_size},L,*
,,L,*
"""
    run_command(f"sfdisk --append {device}", input=partition_table, text=True)
    run_command("partprobe", check=False)
    print("Waiting for device partitions to settle...")
    run_command("udevadm settle")

    part_num = (
        int(
            run_command(
                f"bash -c \"lsblk -l -n -o MAJ:MIN,NAME | grep '{os.path.basename(device)}' | wc -l\"",
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        - 1
    )

    part1, part2, part3, part4, part5, part6, part7 = (
        _get_part_path(device, part_num - 6),
        _get_part_path(device, part_num - 5),
        _get_part_path(device, part_num - 4),
        _get_part_path(device, part_num - 3),
        _get_part_path(device, part_num - 2),
        _get_part_path(device, part_num - 1),
        _get_part_path(device, part_num),
    )

    print("Formatting partitions...")
    format_commands = [
        f"mkfs.fat -F32 -n ESP_A {part1}",
        f"mkfs.fat -F32 -n ESP_B {part2}",
        f"mkfs.ext4 -F -L root_a {part3}",
        f"mkfs.ext4 -F -L root_b {part4}",
        f"mkfs.ext4 -F -L etc_ab {part5}",
        f"mkfs.ext4 -F -L var_ab {part6}",
        f"mkfs.ext4 -F -L home_ab {part7}",
    ]
    for cmd in format_commands:
        run_command(cmd)

    mount_dir = "/mnt/obsidian_install"
    run_command(f"mkdir -p {mount_dir}")
    print("Mounting root partition for slot 'a'...")
    run_command(f"mount /dev/disk/by-label/root_a {mount_dir}")
    print(f"Extracting system from {system_sfs} to slot 'a'...")
    run_command(f"unsquashfs -f -d {mount_dir} -no-xattrs {system_sfs}")
    print("Generating fstab for slot 'a'...")
    fstab_content_a = """
LABEL=root_a  /      ext4  defaults,noatime 0 1
LABEL=ESP_A     /boot  vfat  defaults,noatime 0 2
LABEL=etc_ab  /etc   ext4  defaults,noatime 0 2
LABEL=var_ab  /var   ext4  defaults,noatime 0 2
LABEL=home_ab /home  ext4  defaults,noatime 0 2
"""
    with open(f"{mount_dir}/etc/fstab", "w") as f:
        f.write(fstab_content_a.strip())

    print("Populating shared /etc, /var, and /home partitions...")
    for part_label in ["etc_ab", "var_ab", "home_ab"]:
        fs_dir = part_label.split("_")[0]
        tmp_mount_dir = f"/mnt/tmp_{fs_dir}"
        run_command(f"mkdir -p {tmp_mount_dir}")
        try:
            run_command(f"mount /dev/disk/by-label/{part_label} {tmp_mount_dir}")
            run_command(f"rsync -aK --delete {mount_dir}/{fs_dir}/ {tmp_mount_dir}/")
        finally:
            run_command(f"umount {tmp_mount_dir}", check=False)
            run_command(f"rmdir {tmp_mount_dir}", check=False)

    print("Populating ESP with boot files from system image...")
    esp_tmp_mount = "/mnt/obsidian_esp_tmp"
    run_command(f"mkdir -p {esp_tmp_mount}")
    try:
        run_command(f"mount /dev/disk/by-label/ESP_A {esp_tmp_mount}")
        run_command(f"rsync -aK --delete {mount_dir}/boot/ {esp_tmp_mount}/")
    finally:
        run_command(f"umount {esp_tmp_mount}", check=False)
        run_command(f"rmdir {esp_tmp_mount}", check=False)

    print("Populating ESP_B with boot files from system image...")
    esp_b_tmp_mount = "/mnt/obsidian_esp_b_tmp"
    run_command(f"mkdir -p {esp_b_tmp_mount}")
    try:
        run_command(f"mount /dev/disk/by-label/ESP_B {esp_b_tmp_mount}")
        run_command(f"rsync -aK --delete {mount_dir}/boot/ {esp_b_tmp_mount}/")
    finally:
        run_command(f"umount {esp_b_tmp_mount}", check=False)
        run_command(f"rmdir {esp_b_tmp_mount}", check=False)

    print("Mounting shared partitions for potential chroot...")
    mount_commands = [
        f"mkdir -p {mount_dir}/boot",
        f"mkdir -p {mount_dir}/etc",
        f"mkdir -p {mount_dir}/var",
        f"mkdir -p {mount_dir}/home",
        f"mount /dev/disk/by-label/ESP_A {mount_dir}/boot",
        f"mount /dev/disk/by-label/etc_ab {mount_dir}/etc",
        f"mount /dev/disk/by-label/var_ab {mount_dir}/var",
        f"mount /dev/disk/by-label/home_ab {mount_dir}/home",
    ]
    for cmd in mount_commands:
        run_command(cmd)

    print("Copying support files to slot 'a'...")
    script_path = os.path.realpath(sys.argv[0])
    os_release_path = "/etc/os-release"
    obsidianctl_dest = f"{mount_dir}/usr/bin/obsidianctl"
    if os.path.exists(f"{mount_dir}/obsidianctl-aur-installed"):
        print(
            "obsidianctl has been installed through the AUR. Skipping obsidianctl copy..."
        )
    else:
        run_command(f"mkdir -p {mount_dir}/usr/bin")
        run_command(f"cp {script_path} {obsidianctl_dest}")
        run_command(f"chmod +x {obsidianctl_dest}")
    if os.path.exists(os_release_path):
        run_command(f"cp {os_release_path} {mount_dir}/etc/os-release")
    else:
        print(
            f"Warning: os-release file not found at {os_release_path}. Skipping.",
            file=sys.stderr,
        )

    print("\nSlot 'a' is now configured and mounted.")
    chroot_confirm = input(
        "Do you want to chroot into slot 'a' to make changes before copying it to slot B? (y/N): "
    )
    if chroot_confirm.lower() == "y":
        print(f"Entering chroot environment in {mount_dir}...")
        print(
            "Common tasks: passwd, ln -sf /usr/share/zoneinfo/Region/City /etc/localtime, useradd"
        )
        print("Type 'exit' or press Ctrl+D when you are finished.")
        run_command(f"arch-chroot {mount_dir}", check=False)
        print("Exited chroot.")

    print("Unmounting slot 'a' partitions before copy...")
    run_command(f"umount -R {mount_dir}")
    print("Copying system to slot 'b'...")
    run_command(f"pv \"{part3}\" | dd oflag=sync of={part4} bs=16M")
    run_command(f"e2label {part4} root_b")
    print("Correcting fstab for slot 'b'...")
    mount_b_dir = "/mnt/obsidian_install_b"
    run_command(f"mkdir -p {mount_b_dir}")
    try:
        run_command(f"mount {part4} {mount_b_dir}")
        fstab_b_path = f"{mount_b_dir}/etc/fstab"
        if not os.path.exists(os.path.dirname(fstab_b_path)):
            run_command(f"mkdir -p {os.path.dirname(fstab_b_path)}")
        fstab_content_b = fstab_content_a.replace(
            "LABEL=root_a", "LABEL=root_b"
        ).replace("LABEL=ESP_A", "LABEL=ESP_B")
        with open(fstab_b_path, "w") as f:
            f.write(fstab_content_b)
    finally:
        run_command(f"umount {mount_b_dir}", check=False)
        run_command(f"rm -r {mount_b_dir}", check=False)

    print("Installing systemd-boot to ESP_A...")
    esp_a_mount_dir = "/mnt/obsidian_esp_a"
    run_command(f"mkdir -p {esp_a_mount_dir}")
    try:
        run_command(f"mount {part1} {esp_a_mount_dir}")
        run_command(
            f'bootctl --esp-path={esp_a_mount_dir} --efi-boot-option-description="ObsidianOS (Slot A)" install'
        )
    finally:
        run_command(f"umount {esp_a_mount_dir}", check=False)
        run_command(f"rm -r {esp_a_mount_dir}", check=False)

    print("Installing systemd-boot to ESP_B...")
    esp_b_mount_dir = "/mnt/obsidian_esp_b"
    run_command(f"mkdir -p {esp_b_mount_dir}")
    try:
        run_command(f"mount {part2} {esp_b_mount_dir}")
        run_command(
            f'bootctl --esp-path={esp_b_mount_dir} --efi-boot-option-description="ObsidianOS (Slot B)" install'
        )
    finally:
        run_command(f"umount {esp_b_mount_dir}", check=False)
        run_command(f"rm -r {esp_b_mount_dir}", check=False)

    root_a_partuuid = run_command(
        f"blkid -s PARTUUID -o value {part3}", capture_output=True, text=True
    ).stdout.strip()
    root_b_partuuid = run_command(
        f"blkid -s PARTUUID -o value {part4}", capture_output=True, text=True
    ).stdout.strip()
    if not root_a_partuuid or not root_b_partuuid:
        print(
            "Could not determine PARTUUIDs for root partitions. Cannot create boot entries.",
            file=sys.stderr,
        )
        sys.exit(1)

    loader_conf = """
timeout 3
default obsidian-a.conf
"""
    entry_a_conf = f"""
title ObsidianOS (Slot A)
linux /vmlinuz-linux
initrd /initramfs-linux.img
options root=PARTUUID={root_a_partuuid} rw
"""
    entry_b_conf = f"""
title ObsidianOS (Slot B)
linux /vmlinuz-linux
initrd /initramfs-linux.img
options root=PARTUUID={root_b_partuuid} rw
"""

    esp_a_config_mount_dir = "/mnt/obsidian_esp_a_config"
    run_command(f"mkdir -p {esp_a_config_mount_dir}")
    try:
        run_command(f"mount {part1} {esp_a_config_mount_dir}")
        run_command(f"mkdir -p {esp_a_config_mount_dir}/loader/entries")
        with open(f"{esp_a_config_mount_dir}/loader/loader.conf", "w") as f:
            f.write(loader_conf)
        with open(f"{esp_a_config_mount_dir}/loader/entries/obsidian-a.conf", "w") as f:
            f.write(entry_a_conf)
        with open(f"{esp_a_config_mount_dir}/loader/entries/obsidian-b.conf", "w") as f:
            f.write(entry_b_conf)
    finally:
        run_command(f"umount {esp_a_config_mount_dir}", check=False)
        run_command(f"rm -r {esp_a_config_mount_dir}", check=False)

    print("Writing boot configuration to ESP_B...")
    esp_b_config_mount_dir = "/mnt/obsidian_esp_b_config"
    run_command(f"mkdir -p {esp_b_config_mount_dir}")
    try:
        run_command(f"mount {part2} {esp_b_config_mount_dir}")
        run_command(f"mkdir -p {esp_b_config_mount_dir}/loader/entries")
        with open(f"{esp_b_config_mount_dir}/loader/loader.conf", "w") as f:
            f.write(loader_conf)
        with open(f"{esp_b_config_mount_dir}/loader/entries/obsidian-a.conf", "w") as f:
            f.write(entry_a_conf)
        with open(f"{esp_b_config_mount_dir}/loader/entries/obsidian-b.conf", "w") as f:
            f.write(entry_b_conf)
    finally:
        run_command(f"umount {esp_b_config_mount_dir}", check=False)
        run_command(f"rm -r {esp_b_config_mount_dir}", check=False)

    print("Detecting other operating systems...")
    esp_a_config_mount_dir = "/mnt/obsidian_esp_a_config"
    esp_b_config_mount_dir = "/mnt/obsidian_esp_b_config"
    run_command(f"mkdir -p {esp_a_config_mount_dir}")
    run_command(f"mkdir -p {esp_b_config_mount_dir}")
    try:
        run_command(f"mount {part1} {esp_a_config_mount_dir}")
        run_command(f"mount {part2} {esp_b_config_mount_dir}")
        os_prober_output = run_command(
            "os-prober", capture_output=True, text=True
        ).stdout.strip()
        if os_prober_output:
            print("Found other operating systems:")
            print(os_prober_output)
            esp_a_entries_path = f"{esp_a_config_mount_dir}/loader/entries"
            esp_b_entries_path = f"{esp_b_config_mount_dir}/loader/entries"
            for i, line in enumerate(os_prober_output.splitlines()):
                parts = line.split(":")
                if len(parts) >= 3:
                    device_path = parts[0]
                    os_name = parts[1]
                    entry_filename = f"50-other-os-{i}.conf"
                    entry_content = f"""title {os_name}
efi {device_path}
"""
                    with open(f"{esp_a_entries_path}/{entry_filename}", "w") as f:
                        f.write(entry_content)
                    with open(f"{esp_b_entries_path}/{entry_filename}", "w") as f:
                        f.write(entry_content)
                    print(f"Created boot entry for {os_name}")

        else:
            print("No other operating systems found.")
    except Exception as e:
        print(f"Error running os-prober: {e}")
        print("Please make sure os-prober is installed.")
    finally:
        run_command(f"umount {esp_a_config_mount_dir}", check=False)
        run_command(f"rm -r {esp_a_config_mount_dir}", check=False)
        run_command(f"umount {esp_b_config_mount_dir}", check=False)
        run_command(f"rm -r {esp_b_config_mount_dir}", check=False)

    run_command(f"rm -r {mount_dir}", check=False)
    print("\nInstallation complete!")
    print("Default boot order will attempt Slot A, then Slot B.")
    print("Reboot your system to apply changes.")
