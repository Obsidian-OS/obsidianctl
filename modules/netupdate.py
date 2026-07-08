def handle_netupdate(iguessbro):
    checkroot()
    if not os.path.exists("/etc/is-pillar"):
        print(
            "Error: This system doesn't appear to be running ObsidianOS Atomic. Netupdate functionality is only supported on ObsidianOS Atomic.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Starting Netupdate...")
    print("WARNING: This will download and apply a system update to the inactive slot.")
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != "y":
        print("Operation Canceled.")
        exit(1)
    print("Getting latest image...")
    sudohome = os.env("SUDO_HOME")
    os.system(
        f"bash -c \"curl -fSL $(cat /etc/is-pillar)/latest.erofs -o {sudohome}/.update.erofs\""
    )
    handle_update(argparse.Namespace(slot="a" if get_current_slot()=="b" else "b", system_sfs=f"{sudohome}/.update.erofs", is_pillar=True))
    os.system(f"{sudohome}/.update.erofs")
