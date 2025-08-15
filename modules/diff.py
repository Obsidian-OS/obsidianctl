def handle_slot_diff(args):
    checkroot()
    current = get_current_slot()
    inactive = "b" if current == "a" else "a"
    mount_current = f"/mnt/obsidian_slot_{current}"
    mount_inactive = f"/mnt/obsidian_slot_{inactive}"
    os.makedirs(mount_current, exist_ok=True)
    os.makedirs(mount_inactive, exist_ok=True)
    part_current = f"/dev/disk/by-label/root_{current}"
    part_inactive = f"/dev/disk/by-label/root_{inactive}"
    run_command(f"mount {part_current} {mount_current}")
    run_command(f"mount {part_inactive} {mount_inactive}")
    kernel_current = "unknown"
    kernel_inactive = "unknown"
    boot_current = os.path.join(mount_current, "boot")
    boot_inactive = os.path.join(mount_inactive, "boot")
    if os.path.exists(boot_current):
        for f in os.listdir(boot_current):
            if f.startswith("vmlinuz"):
                kernel_current = f.replace("vmlinuz-", "")
    if os.path.exists(boot_inactive):
        for f in os.listdir(boot_inactive):
            if f.startswith("vmlinuz"):
                kernel_inactive = f.replace("vmlinuz-", "")

    pkgs_current = set()
    pkgs_inactive = set()
    pacman_current = os.path.join(mount_current, "var/lib/pacman/local")
    pacman_inactive = os.path.join(mount_inactive, "var/lib/pacman/local")
    if os.path.exists(pacman_current):
        pkgs_current = {d.split("-")[0] for d in os.listdir(pacman_current)}
    if os.path.exists(pacman_inactive):
        pkgs_inactive = {d.split("-")[0] for d in os.listdir(pacman_inactive)}

    added = sorted(pkgs_inactive - pkgs_current)
    removed = sorted(pkgs_current - pkgs_inactive)
    print(f">> {current}->{inactive} Kernel: {kernel_current}->{kernel_inactive}")
    print(f">> Packages {current}->{inactive}:")
    for p in added:
        print(f"+ {p}")
    for p in removed:
        print(f"- {p}")

    run_command(f"umount {mount_current}")
    run_command(f"umount {mount_inactive}")
    os.rmdir(mount_current)
    os.rmdir(mount_inactive)
