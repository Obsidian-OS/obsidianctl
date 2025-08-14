import os
import subprocess
import shutil
import sys
import time

def handle_enter(args):
    if os.geteuid() != 0:
        print("This command must be run as root.", file=sys.stderr)
        sys.exit(1)

    slot = args.slot
    root_label = f"root_{slot}"
    root_partition = f"/dev/disk/by-label/{root_label}"
    mount_point = f"/mnt/obsidian_{slot}"

    if not os.path.exists(root_partition):
        print(f"Root partition for slot {slot} ({root_partition}) not found.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(mount_point):
        os.makedirs(mount_point)

    try:
        subprocess.run(["mount", root_partition, mount_point], check=True)

        for shared_part in ["etc_ab", "var_ab", "home_ab"]:
            shared_partition = f"/dev/disk/by-label/{shared_part}"
            if os.path.exists(shared_partition):
                fs_dir = shared_part.split("_")[0]
                target_mount = os.path.join(mount_point, fs_dir)
                if not os.path.exists(target_mount):
                    os.makedirs(target_mount)
                subprocess.run(["mount", shared_partition, target_mount], check=True)

        if shutil.which("arch-chroot"):
            print(f"Using arch-chroot to enter slot {slot}...")
            
            cmd = ["arch-chroot"]
            if not args.enable_networking:
                cmd.append("-r")
            
            cmd.append(mount_point)
            subprocess.run(cmd, check=True)
        else:
            print("arch-chroot not found, performing manual chroot...")
            if args.mount_essentials:
                for essential_fs in ["proc", "sys", "dev", "dev/pts", "dev/shm"]:
                    target_mount = os.path.join(mount_point, essential_fs)
                    if not os.path.exists(target_mount):
                        os.makedirs(target_mount, exist_ok=True)
                    subprocess.run(["mount", "--bind", f"/{essential_fs}", target_mount], check=True)

            if args.enable_networking:
                if os.path.exists("/etc/resolv.conf"):
                    os.makedirs(os.path.join(mount_point, "etc"), exist_ok=True)
                    subprocess.run(["cp", "/etc/resolv.conf", os.path.join(mount_point, "etc/resolv.conf")], check=True)

            if args.mount_home:
                home_mount = os.path.join(mount_point, "home")
                if not os.path.exists(home_mount):
                    os.makedirs(home_mount)
                subprocess.run(["mount", "--bind", "/home", home_mount], check=True)
            
            if args.mount_root:
                root_mount = os.path.join(mount_point, "root")
                if not os.path.exists(root_mount):
                    os.makedirs(root_mount)
                subprocess.run(["mount", "--bind", "/root", root_mount], check=True)

            os.chroot(mount_point)
            os.chdir("/")
            
            shell = os.environ.get("SHELL", "/bin/bash")
            subprocess.run([shell], check=True)

    finally:
        print("Exiting chroot and unmounting filesystems...")
        for i in range(5):
            try:
                subprocess.run(["umount", "-R", mount_point], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        
        if os.path.ismount(mount_point):
            print(f"Could not unmount {mount_point}. Please unmount it manually.", file=sys.stderr)
