def handle_status(args):
    logo = [
        "\033[0;36m *+++%\033[0;37m",
        "\033[0;36m****##%\033[0;37m",
        "\033[0;36m#***#\033[0;34m@ \033[0;34m@\033[0;37m",
        " \033[0;34m@     @  @\033[0;37m",
        "   \033[0;34m@    @  @\033[0;37m",
        "    \033[0;34m@  \033[0;35m#****#\033[0;37m",
        "     \033[0;35m@ ######\033[0;37m",
        "        \033[0;35m###%\033[0;37m"
    ]
    info = {}
    info["Active Slot"] = get_current_slot_systemd()
    info["Current Slot"] = get_current_slot()
    info["Kernel"] = run_command(
        "uname -r", capture_output=True, text=True
    ).stdout.strip()
    info["Uptime"] = (
        run_command("uptime -p", capture_output=True, text=True)
        .stdout.strip()
        .replace("up ", "")
    )
    try:
        with open("/etc/os-release") as f:
            os_release = dict(line.strip().split("=", 1) for line in f if "=" in line)
        info["OS"] = os_release.get("PRETTY_NAME", "GNU/Linux").strip('"')
    except FileNotFoundError:
        info["OS"] = "GNU/Linux"

    info["Hostname"] = run_command(
        "hostnamectl hostname", capture_output=True, text=True
    ).stdout.strip()
    cpu_info = run_command("lscpu", capture_output=True, text=True).stdout
    cpu_model_match = re.search(r"Model name:\s+(.*)", cpu_info)
    if cpu_model_match:
        info["CPU"] = cpu_model_match.group(1).strip()

    mem_info = run_command("free -h", capture_output=True, text=True).stdout
    mem_line = mem_info.split("\n")[1]
    mem_parts = mem_line.split()
    if len(mem_parts) >= 3:
        info["Memory"] = f"{mem_parts[2]} / {mem_parts[1]}"

    max_logo_width = max(len(line) for line in logo)
    for i in range(max(len(logo), len(info))):
        logo_line = logo[i] if i < len(logo) else " " * max_logo_width
        if i < len(info):
            key, value = list(info.items())[i]
            info_line = f"\033[1m{key}\033[0m: {value}"
        else:
            info_line = ""

        print(f"{logo_line}  {info_line}")
    print("\n\033[1mPartition Information:\033[0m")
    run_command("lsblk -o NAME,LABEL,SIZE,MOUNTPOINT")
