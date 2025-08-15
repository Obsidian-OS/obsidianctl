def handle_netupdate(args):
    checkroot()
    if args.break_system or not os.path.exists(
        "/etc/obsidianctl-netupdate-enable-DONOTDELETE"
    ):
        print(
            "Error: Image not found to be default image. It is not reccomended to continue.",
            file=sys.stderr,
        )
        print(
            "If you would like to continue... REMOVING ALL NON DEFAULT PACKAGES AND USERS, add the --break-system flag.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Starting image netupdate...")
    print("Getting latest image...")
    os.system(
        "curl https://github.com/Obsidian-OS/archiso/releases/download/latest/system.sfs -o /tmp/system.sfs"
    )
    handle_update(argparse.Namespace(slot=args.slot, system_sfs="/tmp/system.sfs"))
