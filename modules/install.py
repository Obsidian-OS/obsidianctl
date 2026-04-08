def _detect_chroot_cmd():
    import shutil, subprocess

    def _read_os_release():
        vals = {}
        for path in ("/etc/os-release", "/usr/lib/os-release"):
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            vals[k.strip()] = v.strip().strip('"')
            except FileNotFoundError:
                continue
        return vals

    os_release = _read_os_release()
    distro_id = os_release.get("ID", "").lower()
    distro_id_like = os_release.get("ID_LIKE", "").lower()

    # Arch and anything derived from it (Manjaro, EndeavourOS, etc.)
    is_arch_like = "arch" in distro_id or "arch" in distro_id_like

    if is_arch_like and shutil.which("arch-chroot"):
        def do_chroot(mount_dir, *extra_args, check=True):
            cmd = f"arch-chroot {mount_dir}"
            if extra_args:
                cmd += " " + " ".join(extra_args)
            run_command(cmd, check=check)
        return do_chroot
    else:
        # Generic chroot: manually bind-mount proc/sys/dev, run command, unmount
        def do_chroot(mount_dir, *extra_args, check=True):
            import subprocess
            mounts = [
                f"mount -t proc /proc {mount_dir}/proc",
                f"mount --rbind /sys {mount_dir}/sys",
                f"mount --make-rslave {mount_dir}/sys",
                f"mount --rbind /dev {mount_dir}/dev",
                f"mount --make-rslave {mount_dir}/dev",
            ]
            for m in mounts:
                run_command(m, check=False)
            cmd = f"chroot {mount_dir}"
            if extra_args:
                cmd += " " + " ".join(extra_args)
            run_command(cmd, check=check)
            run_command(f"umount -R {mount_dir}/proc {mount_dir}/sys {mount_dir}/dev", check=False)
        return do_chroot

# Detect once at module load time so all handle_* functions share the same instance
_chroot = _detect_chroot_cmd()


def handle_mkobsidiansfs(args):
    _, ext = os.path.splitext(args.system_sfs)
    is_gentoo = ext == ".mkobsfs-gentoo"
    script_name = "mkobsidiansfs-gentoo" if is_gentoo else "mkobsidiansfs"
    repo_url = "https://github.com/Obsidian-OS/mkobsidiansfs/"
    tmp_dir = "/tmp/mkobsidiansfs"
    tmp_script = f"{tmp_dir}/{script_name}"

    out_sfs = "/tmp/tmp_system.sfs" if is_gentoo else "tmp_system.sfs"
    if shutil.which(script_name):
        os.system(f"{script_name} {args.system_sfs} {out_sfs}")
    else:
        if shutil.which("git"):
            os.system(
                f"git clone {repo_url} {tmp_dir};"
                f"chmod u+x {tmp_script};"
                f"{tmp_script} {args.system_sfs} {out_sfs}"
            )
        else:
            print(
                "No git or mkobsidiansfs found. Please install one of these to directly pass in an .mkobsfs."
            )
            sys.exit(1)
    args.system_sfs = out_sfs
    handle_install(args)
    os.remove(out_sfs)


def handle_install(args):
    checkroot()
    device = args.device
    system_sfs = args.system_sfs or "/etc/system.sfs"
    _, ext = os.path.splitext(system_sfs)
    if ext in (".mkobsfs", ".mkobsfs-gentoo"):
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
    fstype="ext4"
    if args.use_f2fs:
        print(f"WARNING: F2FS is a filesystem ONLY for fragile NAND.")
        confirm = input("This is only for advanced users. Are you sure you want to proceed? (y/N): ")
        if confirm.lower() != "y":
            fstype="ext4"
        else:
            fstype="f2fs"
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

    # Wait for partitions to settle after formatting
    run_command("partprobe", check=False)
    run_command("udevadm settle")

    mount_dir = "/mnt/obsidian_install"
    run_command(f"mkdir -p {mount_dir}")
    print("Mounting root partition for slot 'a'...")
    run_command(f"mount {lordo('root_a', device)} {mount_dir}")
    print(f"Extracting system from {system_sfs} to slot 'a'...")
    run_command(f"unsquashfs -f -d {mount_dir} -no-xattrs {system_sfs}")
    print("Generating fstab for slot 'a'...")
    # On OpenRC, /run is cleared at boot so /run/etc_ab needs to be created
    # before localmount processes fstab. 
    import os as _os
    _is_openrc = _os.path.exists(f"{mount_dir}/sbin/openrc-init")
    if _is_openrc:
        _os.makedirs(f"{mount_dir}/etc/init.d", exist_ok=True)
        with open(f"{mount_dir}/etc/init.d/obsidian-mkmountpoints", "w") as _f:
            _f.write("#!/sbin/openrc-run\ndescription=\"Create ObsidianOS mount points in /run\"\ndepend() {\n    before localmount\n    keyword -prefix\n}\nstart() {\n    mkdir -p /run/etc_ab\n}\n")
        _os.chmod(f"{mount_dir}/etc/init.d/obsidian-mkmountpoints", 0o755)
        _os.makedirs(f"{mount_dir}/etc/runlevels/sysinit", exist_ok=True)
        _dst = f"{mount_dir}/etc/runlevels/sysinit/obsidian-mkmountpoints"
        if not _os.path.exists(_dst):
            _os.symlink("/etc/init.d/obsidian-mkmountpoints", _dst)
    fstab_content_a = f"""
{lordo('root_a', device)}  /      {fstype}  defaults,noatime 0 1
{lordo('ESP_A', device)}     /efi  vfat  defaults,noatime 0 2
{lordo('etc_ab', device)}  /run/etc_ab   {fstype}  defaults,noatime 0 2
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
        f"mkdir -p {mount_dir}/efi",
        f"mkdir -p {mount_dir}/etc",
        f"mkdir -p {mount_dir}/var",
        f"mkdir -p {mount_dir}/home",
        f"mount {lordo('ESP_A', device)} {mount_dir}/efi",
        f"mount {lordo('etc_ab', device)} {mount_dir}/run/etc_ab --mkdir",
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
        _chroot(mount_dir, check=False)
        print("Exited chroot.")

    if args.secure_boot:
        print("Setting up Secure Boot...")
        _chroot(mount_dir, "sbctl create-keys || true", check=False)
        _chroot(mount_dir, "sbctl sign-all || true", check=False)

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
{lordo('ESP_B', device)}     /efi  vfat  defaults,noatime 0 2
{lordo('etc_ab', device)}  /run/etc_ab   {fstype}  defaults,noatime 0 2
{lordo('var_ab', device)}  /var   {fstype}  defaults,noatime 0 2
{lordo('home_ab', device)} /home  {fstype}  defaults,noatime 0 2
""")
    finally:
        run_command(f"umount {mount_b_dir}", check=False)
        run_command(f"rm -r {mount_b_dir}", check=False)

    if not args.use_systemdboot:
        mount_dir="/mnt/obsidianos-install-grub"
        print("Installing GRUB to ESP_A...")
        run_command(f"mkdir -p {mount_dir}")
        mount_commands = [
            f"mount {lordo('root_a', device)} {mount_dir}/",
            f"mount {lordo('ESP_A', device)} {mount_dir}/efi",
            f"mount {lordo('etc_ab', device)} {mount_dir}/run/etc_ab --mkdir",
            f"mount {lordo('var_ab', device)} {mount_dir}/var",
            f"mount {lordo('home_ab', device)} {mount_dir}/home",
        ]
        for cmd in mount_commands:
            run_command(cmd)
        if args.use_grub2:
            _chroot(mount_dir, "grub2-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=ObsidianOSslotA")
            _chroot(mount_dir, "sed -i 's|^#*GRUB_DISABLE_OS_PROBER=.*|GRUB_DISABLE_OS_PROBER=false|' /etc/default/grub")
            run_command(f"umount {mount_dir}/efi")
            run_command(f"mkdir {mount_dir}/efi/grub/ -p")
            _chroot(mount_dir, "grub2-mkconfig -o /boot/grub/grub.cfg")
        else:
            _chroot(mount_dir, "grub-install --target=x86_64-efi --efi-directory=/efi =/efi --bootloader-id=ObsidianOSslotA")
            _chroot(mount_dir, "sed -i 's|^#*GRUB_DISABLE_OS_PROBER=.*|GRUB_DISABLE_OS_PROBER=false|' /etc/default/grub")
            # Detect OpenRC and set init=/sbin/openrc-init in kernel cmdline
            import os as _os
            _is_openrc = _os.path.exists(f"{mount_dir}/sbin/openrc-init")
            if _is_openrc:
                run_command(f"sed -i 's|^#*GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"init=/sbin/openrc-init\"|' {mount_dir}/etc/default/grub")
            # Bind-mount ESP to /boot so grub-mkconfig can find the kernel
            run_command(f"mkdir -p {mount_dir}/boot")
            run_command(f"mount --bind {mount_dir}/efi {mount_dir}/boot")
            run_command(f"mkdir -p {mount_dir}/efi/grub")
            _chroot(mount_dir, "grub-mkconfig -o /efi/grub/grub.cfg")
            run_command(f"umount {mount_dir}/boot")
            run_command(f"umount {mount_dir}/efi")
        run_command(f"umount -R {mount_dir}")
        mount_commands = [
            f"mount {lordo('root_b', device)} {mount_dir}/",
            f"mount {lordo('ESP_B', device)} {mount_dir}/efi",
            f"mount {lordo('etc_ab', device)} {mount_dir}/run/etc_ab --mkdir",
            f"mount {lordo('var_ab', device)} {mount_dir}/var",
            f"mount {lordo('home_ab', device)} {mount_dir}/home",
        ]
        for cmd in mount_commands:
            run_command(cmd)
        if args.use_grub2:
            _chroot(mount_dir, "grub2-install --target=x86_64-efi --efi-directory=/efi --boot-directory=/boot --bootloader-id=ObsidianOSslotB")
            run_command(f"umount {mount_dir}/efi")
            run_command(f"mkdir {mount_dir}/efi/grub/ -p")
            _chroot(mount_dir, "grub2-mkconfig -o /boot/grub/grub.cfg")
        else:
            _chroot(mount_dir, "grub-install --target=x86_64-efi --efi-directory=/efi --boot-directory=/boot --bootloader-id=ObsidianOSslotB")
            # Detect OpenRC and set init=/sbin/openrc-init in kernel cmdline
            import os as _os
            _is_openrc = _os.path.exists(f"{mount_dir}/sbin/openrc-init")
            if _is_openrc:
                run_command(f"sed -i 's|^#*GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"init=/sbin/openrc-init\"|' {mount_dir}/etc/default/grub")
            # Bind-mount ESP to /boot so grub-mkconfig can find the kernel
            run_command(f"mkdir -p {mount_dir}/boot")
            run_command(f"mount --bind {mount_dir}/efi {mount_dir}/boot")
            run_command(f"mkdir -p {mount_dir}/efi/grub")
            _chroot(mount_dir, "grub-mkconfig -o /efi/grub/grub.cfg")
            run_command(f"umount {mount_dir}/boot")
            run_command(f"umount {mount_dir}/efi")
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
            run_command(f'bootctl --esp-path={esp_b_mount_dir} --efi-boot-option-description="ObsidianOS (Slot B)" install')
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
