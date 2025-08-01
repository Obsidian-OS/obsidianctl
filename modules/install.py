
def handle_install(args):
    device = args.device
    system_sfs = args.system_sfs
    if not os.path.exists(device):
        print(f"Error: Device '{device}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(system_sfs):
        print(f"Error: System image '{system_sfs}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"WARNING: This will destroy all data on {device}.")
    confirm = input("Are you sure you want to proceed? (y/N): ")
    if confirm.lower() != "y":
        print("Installation aborted.")
        sys.exit(0)
    print("Partitioning device...")
    partition_table = """
label: gpt
,512M,U,*
,5G,L,*
,5G,L,*
,5G,L,*
,5G,L,*
,,L,*
"""
    run_command(f"sfdisk {device}", input=partition_table, text=True)
    run_command("partprobe", check=False)
    print("Waiting for device partitions to settle...")
    run_command("udevadm settle")
    part1, part2, part3, part4, part5, part6 = (
        _get_part_path(device, 1),
        _get_part_path(device, 2),
        _get_part_path(device, 3),
        _get_part_path(device, 4),
        _get_part_path(device, 5),
        _get_part_path(device, 6),
    )

    print("Formatting partitions...")
    format_commands = [
        f"mkfs.fat -F32 -n ESP {part1}",
        f"mkfs.ext4 -F -L root_a {part2}",
        f"mkfs.ext4 -F -L root_b {part3}",
        f"mkfs.ext4 -F -L etc_ab {part4}",
        f"mkfs.ext4 -F -L var_ab {part5}",
        f"mkfs.ext4 -F -L home_ab {part6}",
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
LABEL=ESP     /boot  vfat  defaults,noatime 0 2
LABEL=etc_ab  /etc   ext4  defaults,noatime 0 2
LABEL=var_ab  /var   ext4  defaults,noatime 0 2
LABEL=home_ab /home  ext4  defaults,noatime 0 2
"""
    with open(f"{mount_dir}/etc/fstab", "w") as f:
        f.write(fstab_content_a.strip())

    print("Populating shared /etc and /var partitions...")
    for part_label in ["etc_ab", "var_ab"]:
        fs_dir = part_label.split('_')[0]
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
        run_command(f"mount /dev/disk/by-label/ESP {esp_tmp_mount}")
        run_command(f"rsync -aK --delete {mount_dir}/boot/ {esp_tmp_mount}/")
    finally:
        run_command(f"umount {esp_tmp_mount}", check=False)
        run_command(f"rmdir {esp_tmp_mount}", check=False)

    print("Mounting shared partitions for potential chroot...")
    mount_commands = [
        f"mkdir -p {mount_dir}/boot",
        f"mkdir -p {mount_dir}/etc",
        f"mkdir -p {mount_dir}/var",
        f"mkdir -p {mount_dir}/home",
        f"mount /dev/disk/by-label/ESP {mount_dir}/boot",
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
    run_command(f"dd if={part2} of={part3} bs=16M status=progress")
    run_command(f"e2label {part3} root_b")
    print("Correcting fstab for slot 'b'...")
    mount_b_dir = "/mnt/obsidian_install_b"
    run_command(f"mkdir -p {mount_b_dir}")
    try:
        run_command(f"mount {part3} {mount_b_dir}")
        fstab_b_path = f"{mount_b_dir}/etc/fstab"
        if not os.path.exists(os.path.dirname(fstab_b_path)):
            run_command(f"mkdir -p {os.path.dirname(fstab_b_path)}")
        fstab_content_b = fstab_content_a.replace("LABEL=root_a", "LABEL=root_b")
        with open(fstab_b_path, "w") as f:
            f.write(fstab_content_b)
    finally:
        run_command(f"umount {mount_b_dir}", check=False)
        run_command(f"rm -r {mount_b_dir}")

    print("Setting up bootloader entries...")
    esp_mount_dir = "/mnt/obsidian_esp_check"
    run_command(f"mkdir -p {esp_mount_dir}")
    try:
        run_command(f"mount {part1} {esp_mount_dir}")
        kernel_path = f"{esp_mount_dir}/vmlinuz-linux"
        initramfs_path = f"{esp_mount_dir}/initramfs-linux.img"
        if not os.path.exists(kernel_path) or not os.path.exists(initramfs_path):
            print(
                f"Error: vmlinuz-linux or initramfs-linux.img not found on the ESP partition ({part1}).",
                file=sys.stderr,
            )
            print(
                "This likely means the system image used for installation did not contain a kernel in /boot.",
                file=sys.stderr,
            )
            sys.exit(1)
    finally:
        run_command(f"umount {esp_mount_dir}", check=False)
        run_command(f"rm -r {esp_mount_dir}", check=False)

    root_a_partuuid = run_command(
        f"blkid -s PARTUUID -o value {part2}", capture_output=True, text=True
    ).stdout.strip()
    root_b_partuuid = run_command(
        f"blkid -s PARTUUID -o value {part3}", capture_output=True, text=True
    ).stdout.strip()
    if not root_a_partuuid or not root_b_partuuid:
        print(
            "Could not determine PARTUUIDs for root partitions. Cannot create boot entries.",
            file=sys.stderr,
        )
        sys.exit(1)
    efibootmgr_commands = [
        f"efibootmgr --create --disk {device} --part 1 --label 'ObsidianOS (Slot A)' --loader '\\vmlinuz-linux' --unicode 'root=PARTUUID={root_a_partuuid} rw initrd=\\initramfs-linux.img'",
        f"efibootmgr --create --disk {device} --part 1 --label 'ObsidianOS (Slot B)' --loader '\\vmlinuz-linux' --unicode 'root=PARTUUID={root_b_partuuid} rw initrd=\\initramfs-linux.img'",
    ]
    for cmd in efibootmgr_commands:
        run_command(cmd)
    run_command(f"rm -r {mount_dir}", check=False)
    print("\nInstallation complete!")
    print("Default boot order will attempt Slot A, then Slot B.")
    print("Reboot your system to apply changes.")
