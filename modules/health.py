import os
import sys
import subprocess

def handle_health_check(args):
    """Check the health of both A/B slots"""
    print("🔍 Performing system health check...")
    print("=" * 50)
    
    # Check if we're running from an obsidianctl-managed system
    if not os.path.exists("/dev/disk/by-label/root_a") or not os.path.exists("/dev/disk/by-label/root_b"):
        print("❌ Error: This system was not installed with obsidianctl")
        print("   Health check requires A/B slot configuration")
        sys.exit(1)
    
    current_slot = get_current_slot()
    print(f"📍 Current active slot: {current_slot.upper()}")
    
    # Check both slots
    slots_status = {}
    for slot in ["a", "b"]:
        print(f"\n🔧 Checking slot {slot.upper()}...")
        status = check_slot_health(slot)
        slots_status[slot] = status
        print_slot_status(slot, status)
    
    # Overall health assessment
    print("\n" + "=" * 50)
    print("📊 OVERALL HEALTH ASSESSMENT")
    print("=" * 50)
    
    healthy_slots = sum(1 for status in slots_status.values() if status["overall"] == "healthy")
    total_slots = len(slots_status)
    
    if healthy_slots == total_slots:
        print("✅ All slots are healthy!")
        print("🎯 System is in optimal condition")
    elif healthy_slots > 0:
        print(f"⚠️  {healthy_slots}/{total_slots} slots are healthy")
        print("🔧 Some maintenance may be needed")
    else:
        print("❌ No healthy slots detected!")
        print("🚨 System requires immediate attention")
    
    return slots_status

def check_slot_health(slot):
    """Check the health of a specific slot"""
    status = {
        "overall": "unknown",
        "bootable": False,
        "filesystem": "unknown",
        "kernel": "unknown",
        "packages": "unknown",
        "errors": []
    }
    
    part_path = f"/dev/disk/by-label/root_{slot}"
    
    # Check if partition exists
    if not os.path.exists(part_path):
        status["errors"].append("Partition not found")
        status["overall"] = "critical"
        return status
    
    # Check filesystem integrity
    try:
        result = run_command(f"e2fsck -n {part_path}", capture_output=True, check=False)
        if result.returncode == 0:
            status["filesystem"] = "healthy"
        else:
            status["filesystem"] = "needs_repair"
            status["errors"].append("Filesystem has errors")
    except Exception as e:
        status["filesystem"] = "unknown"
        status["errors"].append(f"Filesystem check failed: {e}")
    
    # Check if slot is bootable
    esp_path = f"/dev/disk/by-label/ESP_{slot.upper()}"
    if os.path.exists(esp_path):
        # Check for bootloader files
        mount_dir = f"/mnt/health_check_esp_{slot}"
        try:
            run_command(f"mkdir -p {mount_dir}")
            run_command(f"mount {esp_path} {mount_dir}")
            
            boot_files = ["loader/loader.conf", "loader/entries/obsidian-a.conf", "loader/entries/obsidian-b.conf"]
            missing_files = []
            
            for boot_file in boot_files:
                if not os.path.exists(os.path.join(mount_dir, boot_file)):
                    missing_files.append(boot_file)
            
            if not missing_files:
                status["bootable"] = True
            else:
                status["errors"].append(f"Missing boot files: {', '.join(missing_files)}")
                
        finally:
            run_command(f"umount {mount_dir}", check=False)
            run_command(f"rmdir {mount_dir}", check=False)
    else:
        status["errors"].append("ESP partition not found")
    
    # Check kernel and packages
    mount_dir = f"/mnt/health_check_{slot}"
    try:
        run_command(f"mkdir -p {mount_dir}")
        run_command(f"mount {part_path} {mount_dir}")
        
        # Check kernel
        boot_dir = os.path.join(mount_dir, "boot")
        if os.path.exists(boot_dir):
            kernels = [f for f in os.listdir(boot_dir) if f.startswith("vmlinuz")]
            if kernels:
                status["kernel"] = kernels[0].replace("vmlinuz-", "")
            else:
                status["errors"].append("No kernel found")
        else:
            status["errors"].append("Boot directory not found")
        
        # Check packages
        pacman_dir = os.path.join(mount_dir, "var/lib/pacman/local")
        if os.path.exists(pacman_dir):
            package_count = len([d for d in os.listdir(pacman_dir) if os.path.isdir(os.path.join(pacman_dir, d))])
            status["packages"] = f"{package_count} packages"
        else:
            status["packages"] = "unknown"
            
    except Exception as e:
        status["errors"].append(f"Mount check failed: {e}")
    finally:
        run_command(f"umount {mount_dir}", check=False)
        run_command(f"rmdir {mount_dir}", check=False)
    
    # Determine overall health
    if status["errors"]:
        if len(status["errors"]) > 2:
            status["overall"] = "critical"
        else:
            status["overall"] = "warning"
    else:
        status["overall"] = "healthy"
    
    return status

def print_slot_status(slot, status):
    """Print the status of a slot in a user-friendly format"""
    health_icons = {
        "healthy": "✅",
        "warning": "⚠️",
        "critical": "❌",
        "unknown": "❓"
    }
    
    print(f"   {health_icons[status['overall']]} Overall: {status['overall'].upper()}")
    print(f"   🚀 Bootable: {'Yes' if status['bootable'] else 'No'}")
    print(f"   💾 Filesystem: {status['filesystem']}")
    print(f"   🐧 Kernel: {status['kernel']}")
    print(f"   📦 Packages: {status['packages']}")
    
    if status["errors"]:
        print(f"   ⚠️  Issues:")
        for error in status["errors"]:
            print(f"      • {error}")

def handle_verify_integrity(args):
    """Verify the integrity of a specific slot"""
    slot = args.slot
    print(f"🔍 Verifying integrity of slot {slot.upper()}...")
    
    part_path = f"/dev/disk/by-label/root_{slot}"
    if not os.path.exists(part_path):
        print(f"❌ Error: Slot '{slot}' not found", file=sys.stderr)
        sys.exit(1)
    
    print("📋 Running filesystem integrity check...")
    try:
        # Run read-only filesystem check
        result = run_command(f"e2fsck -n {part_path}", capture_output=True, check=False)
        
        if result.returncode == 0:
            print("✅ Filesystem integrity check passed")
        else:
            print("❌ Filesystem integrity check failed")
            print(f"   Exit code: {result.returncode}")
            if result.stderr:
                print(f"   Errors: {result.stderr}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Integrity check failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    print("🔍 Checking for corrupted files...")
    mount_dir = f"/mnt/integrity_check_{slot}"
    corrupted_files = []
    
    try:
        run_command(f"mkdir -p {mount_dir}")
        run_command(f"mount {part_path} {mount_dir}")
        
        # Check critical system files
        critical_files = [
            "/etc/fstab",
            "/etc/passwd",
            "/etc/group",
            "/etc/shadow",
            "/boot/vmlinuz-linux",
            "/boot/initramfs-linux.img"
        ]
        
        for file_path in critical_files:
            full_path = os.path.join(mount_dir, file_path.lstrip("/"))
            if os.path.exists(full_path):
                try:
                    with open(full_path, "rb") as f:
                        f.read(1024)  # Try to read first 1KB
                except Exception:
                    corrupted_files.append(file_path)
            else:
                corrupted_files.append(file_path)
        
        if corrupted_files:
            print("❌ Found corrupted or missing critical files:")
            for file_path in corrupted_files:
                print(f"   • {file_path}")
            sys.exit(1)
        else:
            print("✅ All critical files are intact")
            
    finally:
        run_command(f"umount {mount_dir}", check=False)
        run_command(f"rmdir {mount_dir}", check=False)
    
    print("✅ Slot integrity verification completed successfully!") 