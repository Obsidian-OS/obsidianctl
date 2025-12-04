def handle_etc_ab(args):
    checkroot()
    file_path_relative = args.file_path.lstrip("/")
    source_path = os.path.join("/etc", file_path_relative)
    etc_ab_root = "/run/etc_ab"
    dest_path = os.path.join(etc_ab_root, file_path_relative)
    if not os.path.exists(etc_ab_root) or not os.path.isdir(etc_ab_root):
        print(
            "[!] the new ETC_AB mode is not enabled. please migrate to `20251204-etc`.",
            file=sys.stderr,
        )
        sys.exit(1)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(source_path):
        shutil.copy2(source_path, dest_path)
    else:
        print(
            f"[!] '{source_path}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    fstab_entry = (
        f"{dest_path} {source_path} none defaults,nofail,nobootwait,bind 0 0\n"
    )
    os.makedirs(os.path.dirname(source_path), exist_ok=True)
    try:
        with open("/etc/fstab", "a") as f:
            f.write(fstab_entry)
        print(f"[+] added to '{file_path_relative}' to fstab.")
    except Exception as e:
        print(f"[!] error writing to fstab: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        run_command(f"mount {source_path}")
        print(f"[+] file ('{source_path}') is now shared.")
    except Exception as e:
        print(
            f"[?] failed to immediately bind-mount '{source_path}': {e}",
            file=sys.stderr,
        )
