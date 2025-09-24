def handle_mkobsidiansfs(args):
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
    args.system_sfs = "tmp_system.sfs"
    handle_install(args)
    os.remove("tmp_system.sfs")


def handle_install(args):
    checkroot()
    fstype="ext4"
    if args.use_f2fs:
        fstype="f2fs"
    device = args.device
    system_sfs = args.system_sfs or "/etc/system.sfs"
    _, ext = os.path.splitext(system_sfs)
    if ext == ".mkobsfs":
        handle_mkobsidiansfs(args)
        sys.exit()
    if args.dual_boot:
        handle_dual_boot(args)
        return

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
    run_command(f"sfdisk {device}", input=partition_table, text=True)
    run_command("partprobe", check=False)
    print("Waiting for device partitions to settle...")
    run_command("udevadm settle")
    part1, part2, part3, part4, part5, part6, part7 = (
        _get_part_path(device, 1),
        _get_part_path(device, 2),
        _get_part_path(device, 3),
        _get_part_path(device, 4),
        _get_part_path(device, 5),
        _get_part_path(device, 6),
        _get_part_path(device, 7),
    )

    print("Formatting partitions...")
    format_commands = [
        f"mkfs.fat    -F32 -n ESP_A   {part1}",
        f"mkfs.fat    -F32 -n ESP_B   {part2}",
        f"mkfs.{fstype} -F -L root_a  {part3}",
        f"mkfs.{fstype} -F -L root_b  {part4}",
        f"mkfs.{fstype} -F -L etc_ab  {part5}",
        f"mkfs.{fstype} -F -L var_ab  {part6}",
        f"mkfs.{fstype} -F -L home_ab {part7}",
    ]
    for cmd in format_commands:
        run_command(cmd)

    mount_dir = "/mnt/obsidian_install"
    run_command(f"mkdir -p {mount_dir}")
    rint("Mounting root partition for slot 'a'...")
    run_command(f"mount {lordo('root_a', device)} {mount_dir}")
    print(f"Extracting system from {system_sfs} to slot 'a'...")
    run_command(f"unsquashfs -f -d {mount_dir} -no-xattrs {system_sfs}")
    print("Generating fstab for slot 'a'...")
    fstab_content_a = f"""
{lordo('root_a', device)}  /      {fstype}  defaults,noatime 0 1
{lordo('ESP_A', device)}     /boot  vfat  defaults,noatime 0 2
{lordo('etc_ab', device)}  /etc   {fstype}  defaults,noatime 0 2
{lordo('var_ab', device)}  /var   {fstype}  defaults,noatime 0 2
{lordo('home_ab', device)} /home  {fstype}  defaults,noatime 0 2
"""
    with open(f"{mount_dir}/etc/fstab", "w") as f:
        f.write(fstab_content_a.strip())

    print("Populating shared /etc, /var, and /home partitions...")
    for part_label in ["etc_ab", "var_ab", "home_ab"]:
        fs_dir = part_label.split("_")[0]
        tmp_mount_dir = f"/mnt/tmp_{fs_dir}"
        run_command(f"mkdir -p {tmp_mount_dir}")
        try:
            run_command(f"mount {lordo(part_label, device)} {tmp_mount_dir}")
            run_command(f"rsync -aK --delete {mount_dir}/{fs_dir}/ {tmp_mount_dir}/")
        finally:
            run_command(f"umount {tmp_mount_dir}", check=False)
            run_command(f"rmdir {tmp_mount_dir}", check=False)

    print("Populating ESP with boot files from system image...")
    esp_tmp_mount = "/mnt/obsidian_esp_tmp"
    run_command(f"mkdir -p {esp_tmp_mount}")
    try:
        run_command(f"mount {lordo('ESP_A', device)} {esp_tmp_mount}")
        run_command(f"rsync -aK --delete {mount_dir}/boot/ {esp_tmp_mount}/")
    finally:
        run_command(f"umount {esp_tmp_mount}", check=False)
        run_command(f"rmdir {esp_tmp_mount}", check=False)

    print("Populating ESP_B with boot files from system image...")
    esp_b_tmp_mount = "/mnt/obsidian_esp_b_tmp"
    run_command(f"mkdir -p {esp_b_tmp_mount}")
    try:
        run_command(f"mount {lordo('ESP_B', device)} {esp_b_tmp_mount}")
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
        f"mount {lordo('ESP_A', device)} {mount_dir}/boot",
        f"mount {lordo('etc_ab', device)} {mount_dir}/etc",
        f"mount {lordo('var_ab', device)} {mount_dir}/var",
        f"mount {lordo('home_ab', device)} {mount_dir}/home",
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

    if os.path.exists("/usr/share/pixmaps/obsidianos.png"):
        run_command(f"mkdir -p {mount_dir}/usr/share/pixmaps/")
        run_command(
            f"cp /usr/share/pixmaps/obsidianos.png {mount_dir}/usr/share/pixmaps/obsidianos.png"
        )
    else:
        print(
            f"Warning: ObsidianOS Logo file wasn't found. Skipping.",
            file=sys.stderr,
        ) 
    run_command(f"umount {mount_dir}/etc", check=False)

    autostart_service_content = """[Unit]
Description=Force start all enabled services before TTY login
DefaultDependencies=no
After=basic.target
Before=getty.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'systemctl list-unit-files --state=enabled | awk \"{print $1}\" | grep -E ".service$" | xargs -r systemctl start'

[Install]
WantedBy=getty.target
"""
    service_file_path = f"{mount_dir}/etc/systemd/system/obsidianos-autostart.service"
    run_command(f"mkdir -p {os.path.dirname(service_file_path)}")
    with open(service_file_path, "w") as f:
        f.write(autostart_service_content)
    run_command(f"systemctl enable obsidianos-autostart.service --root={mount_dir}")
    run_command(f"mount {lordo('etc_ab', device)} {mount_dir}/etc")
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
    source_mount_point = "/mnt/obsidian_source_a"
    target_mount_point = "/mnt/obsidian_target_b"
    run_command(f"mkdir -p {source_mount_point} {target_mount_point}")
    try:
        run_command(f"mount {part3} {source_mount_point}")
        run_command(f"mount {part4} {target_mount_point}")
        run_command(
            f"rsync -aHAX --inplace --delete --info=progress2 {source_mount_point}/ {target_mount_point}/"
        )
    finally:
        run_command(f"umount {source_mount_point}", check=False)
        run_command(f"umount {target_mount_point}", check=False)
        run_command(f"rm -r {source_mount_point} {target_mount_point}", check=False)
    run_command(f"e2label {part4} root_b")
    print("Correcting fstab for slot 'b'...")
    mount_b_dir = "/mnt/obsidian_install_b"
    run_command(f"mkdir -p {mount_b_dir}")
    try:
        run_command(f"mount {part4} {mount_b_dir}")
        fstab_b_path = f"{mount_b_dir}/etc/fstab"
        if not os.path.exists(os.path.dirname(fstab_b_path)):
            run_command(f"mkdir -p {os.path.dirname(fstab_b_path)}")
        with open(fstab_b_path, "w") as f:
            f.write(f"""
{lordo('root_b', device)}  /      {fstype}  defaults,noatime 0 1
{lordo('ESP_B', device)}     /boot  vfat  defaults,noatime 0 2
{lordo('etc_ab', device)}  /etc   {fstype}  defaults,noatime 0 2
{lordo('var_ab', device)}  /var   {fstype}  defaults,noatime 0 2
{lordo('home_ab', device)} /home  {fstype}  defaults,noatime 0 2
""")
    finally:
        run_command(f"umount {mount_b_dir}", check=False)
        run_command(f"rm -r {mount_b_dir}", check=False)

    if args.grub_install:
        mount_dir="/mnt/obsidianos-install-grub"
        print("Installing GRUB to ESP_A...")
        run_command(f"mkdir -p {mount_dir}")
        mount_commands = [
            f"mount {lordo('root_a', device) {mount_dir}/boot",
            f"mount {lordo('ESP_A', device)} {mount_dir}/boot",
            f"mount {lordo('etc_ab', device)} {mount_dir}/etc",
            f"mount {lordo('var_ab', device)} {mount_dir}/var",
            f"mount {lordo('home_ab', device)} {mount_dir}/home",
        ]
        for cmd in mount_commands:
            run_command(cmd)
        run_command(f"arch-chroot {mount_dir} grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=ObsidianOS-GRUB-A")
        # we do NOT care about fedora... for now. Quick rant: WHY DOES FEDORA AND REHL AND CENTOS AND ROCKY AND OPENSUSE AND SUSE MAINTAIN LEGACY GRUB, REQUIRING US TO USE grub2-install I HATE IT STOP
        run_command(f"arch-chroot {mount_dir} grub-mkconfig -o /boot/grub/grub.cfg")
        run_command(f"umount -R {mount_dir}")
        mount_commands = [
            f"mount {lordo('root_b', device) {mount_dir}/boot",
            f"mount {lordo('ESP_B', device)} {mount_dir}/boot",
            f"mount {lordo('etc_ab', device)} {mount_dir}/etc",
            f"mount {lordo('var_ab', device)} {mount_dir}/var",
            f"mount {lordo('home_ab', device)} {mount_dir}/home",
        ]
        for cmd in mount_commands:
            run_command(cmd)
        run_command(f"arch-chroot {mount_dir} grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=ObsidianOS-GRUB-B")
        run_command(f"arch-chroot {mount_dir} grub-mkconfig -o /boot/grub/grub.cfg")
        run_command(f"umount -R {mount_dir}")
    else:
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
timeout 0
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
    run_command(f"rm -r {mount_dir}", check=False)
    print("\nInstallation complete!")
    print("Default boot order will attempt Slot A, then Slot B.")
    print("Reboot your system to apply changes.")
