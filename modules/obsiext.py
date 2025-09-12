MOUNT_BASE_DIR = "/run/obsidianos-extensions"
FSTAB_PATH = "/etc/fstab"
OVERLAYS_CONF_PATH = "/etc/obsidianos-overlays.conf"
LIB_OVERLAYS_SO = "/usr/lib/libobsidianos_overlays.so"
FSTAB_MARKER_PREFIX = "# OBSIDIANOS_EXT:"
OVERLAYS_MARKER_PREFIX = "# OBSIDIANOS_EXT:"
ENVIRONMENT_FILE = "/etc/environment"
LD_PRELOAD_LINE = "LD_PRELOAD=/usr/lib/libobsidianos_overlays.so"
ENVIRONMENT_MARKER = "# OBSIDIANOS_OVERLAYS"


def _check_lib_exists():
    if not os.path.exists(LIB_OVERLAYS_SO):
        print(f"Error: libobsidianos_overlays is not installed.", file=sys.stderr)
        sys.exit(1)


def _get_extension_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def _read_file_lines(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as f:
        return f.readlines()


def _write_file_lines(filepath, lines):
    with open(filepath, "w") as f:
        f.writelines(lines)


def handle_add_extension(args):
    checkroot()
    _check_lib_exists()
    ext_path = args.path
    if not os.path.exists(ext_path):
        print(f"Error: Extension file '{ext_path}' not found.", file=sys.stderr)
        sys.exit(1)
    if not ext_path.endswith(".obsiext"):
        print(
            f"Error: Extension file '{ext_path}' must have a .obsiext extension.",
            file=sys.stderr,
        )
        sys.exit(1)

    ext_name = _get_extension_name(ext_path)
    dest_path = ext_path
    mount_point = os.path.join(MOUNT_BASE_DIR, ext_name)
    os.makedirs(mount_point, exist_ok=True)
    print(f"Using '{ext_path}' directly as extension source.")
    fstab_entry = f"{dest_path} {mount_point} squashfs defaults,ro,nofail 0 0 {FSTAB_MARKER_PREFIX}{ext_name}\n"
    overlays_entry = f"{mount_point} {OVERLAYS_MARKER_PREFIX}{ext_name}\n"
    fstab_lines = _read_file_lines(FSTAB_PATH)
    overlays_lines = _read_file_lines(OVERLAYS_CONF_PATH)
    for line in fstab_lines:
        if FSTAB_MARKER_PREFIX + ext_name in line:
            print(f"Extension '{ext_name}' already added.", file=sys.stderr)
            sys.exit(0)

    fstab_lines.append(fstab_entry)
    overlays_lines.append(overlays_entry)
    _write_file_lines(FSTAB_PATH, fstab_lines)
    _write_file_lines(OVERLAYS_CONF_PATH, overlays_lines)
    print(
        f"Extension '{ext_name}' added successfully.\nYou may need to reboot or run 'sudo mount -a' for changes to take effect."
    )


def handle_remove_extension(args):
    checkroot()
    _check_lib_exists()
    ext_name = args.name
    fstab_lines = _read_file_lines(FSTAB_PATH)
    overlays_lines = _read_file_lines(OVERLAYS_CONF_PATH)
    new_fstab_lines = []
    removed_fstab_entry = False
    for line in fstab_lines:
        if FSTAB_MARKER_PREFIX + ext_name in line:
            removed_fstab_entry = True
        else:
            new_fstab_lines.append(line)

    new_overlays_lines = []
    removed_overlays_entry = False
    mount_point_to_remove = None
    for line in overlays_lines:
        if OVERLAYS_MARKER_PREFIX + ext_name in line:
            removed_overlays_entry = True
            parts = line.split()
            if parts:
                mount_point_to_remove = parts[0]
        else:
            new_overlays_lines.append(line)

    if not removed_fstab_entry and not removed_overlays_entry:
        print(f"Extension '{ext_name}' not found.", file=sys.stderr)
        sys.exit(1)

    _write_file_lines(FSTAB_PATH, new_fstab_lines)
    _write_file_lines(OVERLAYS_CONF_PATH, new_overlays_lines)

    if mount_point_to_remove and os.path.exists(mount_point_to_remove):
        try:
            os.rmdir(mount_point_to_remove)
            print(f"Removed empty mount point directory '{mount_point_to_remove}'.")
        except OSError as e:
            print(
                f"Warning: Could not remove mount point directory '{mount_point_to_remove}': {e}",
                file=sys.stderr,
            )

    print(
        f"Extension '{ext_name}' removed successfully. You may need to reboot or run 'sudo umount <mount_point>' for changes to take effect."
    )


def handle_list_extensions(args):
    _check_lib_exists()
    fstab_lines = _read_file_lines(FSTAB_PATH)
    fstab_exts = set()
    for line in fstab_lines:
        match = re.search(rf"{FSTAB_MARKER_PREFIX}([\w\d\-\_]+)", line)
        if match:
            fstab_exts.add(match.group(1))

    all_exts = sorted(list(fstab_exts))
    if not all_exts:
        print("No ObsidianOS extensions found.")
        return

    print("ObsidianOS Extensions:")
    for ext in all_exts:
        print(f"- {ext}")


def handle_ext_enable(args):
    checkroot()
    _check_lib_exists()
    env_lines = _read_file_lines(ENVIRONMENT_FILE)
    new_env_lines = []
    found = False
    for line in env_lines:
        if LD_PRELOAD_LINE in line and ENVIRONMENT_MARKER in line:
            found = True
            new_env_lines.append(line)
        elif ENVIRONMENT_MARKER in line:
            continue
        else:
            new_env_lines.append(line)

    if not found:
        new_env_lines.append(f"{LD_PRELOAD_LINE} {ENVIRONMENT_MARKER}\n")
        _write_file_lines(ENVIRONMENT_FILE, new_env_lines)
        print(
            f"Enabled ObsidianOS Overlays. You may need to reboot for changes to take effect."
        )
    else:
        print(f"ObsidianOS Overlay is already enabled.")


def handle_ext_disable(args):
    checkroot()
    _check_lib_exists()
    env_lines = _read_file_lines(ENVIRONMENT_FILE)
    new_env_lines = []
    removed = False
    for line in env_lines:
        if LD_PRELOAD_LINE in line and ENVIRONMENT_MARKER in line:
            removed = True
            continue
        else:
            new_env_lines.append(line)

    if removed:
        _write_file_lines(ENVIRONMENT_FILE, new_env_lines)
        print(
            f"Disabled ObsidianOS Overlays. You may need to reboot for changes to take effect."
        )
    else:
        print(f"ObsidianOS Overlay is already disabled or not found with marker.")


def handle_ext(args):
    if args.ext_command == "add":
        handle_add_extension(args)
    elif args.ext_command == "rm":
        handle_remove_extension(args)
    elif args.ext_command == "list":
        handle_list_extensions(args)
    elif args.ext_command == "enable":
        handle_ext_enable(args)
    elif args.ext_command == "disable":
        handle_ext_disable(args)
    else:
        print(
            "Invalid 'ext' command. Use 'add', 'rm', 'list', 'enable', or 'disable'.",
            file=sys.stderr,
        )
        sys.exit(1)

