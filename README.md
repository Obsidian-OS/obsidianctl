# obsidianctl

`obsidianctl` is a command-line utility designed to manage A/B boot slots and shared partitions on ObsidianOS systems. It provides functionalities for system installation, status monitoring, active slot switching, and updating system images.

## Features

*   **`status`**: Display current active A/B slot and detailed system information in a neofetch-like format.
*   **`install`**: Partition a target device and install a SquashFS system image onto both A and B slots, setting up shared `/etc`, `/var`, and `/home` partitions, and configuring UEFI boot entries.
*   **`switch`**: Change the active boot slot (A or B) for the next boot, persistently.
*   **`update`**: Update a specific A/B slot with a new SquashFS system image.
*   **`sync`**: Clone the current slot's root and ESP partitions to the other slot using `dd`.
*   **`backup-slot`**: Create a compressed backup of a specific slot with metadata.
*   **`rollback-slot`**: Restore a slot from a previous backup.
*   **`health-check`**: Comprehensive health assessment of both A/B slots.
*   **`verify-integrity`**: Verify filesystem integrity and check for corrupted files.

## Install (AUR)

`obsidianctl` is in the AUR as [obsidianctl](https://aur.archlinux.org/packages/obsidianctl) and [obsidianctl-git](https://aur.archlinux.org/packages/obsidianctl-git). You can install it as follows:

### Stable version (latest release, does not include unreleased changes)

```bash
yay -S obsidianctl
```

### Git version (not very stable, contains unreleased changes)

```bash
yay -S obsidianctl-git
```

Or with your favorite [AUR helper](https://wiki.archlinux.org/title/AUR_helpers).

## Prerequisites

`obsidianctl` requires root privileges to operate. It relies on several standard Linux utilities. Ensure the following commands are available on your system:

*   `efibootmgr`
*   `sfdisk`
*   `partprobe`
*   `udevadm`
*   `mkfs.fat`
*   `mkfs.ext4`
*   `unsquashfs` (from `squashfs-tools`)
*   `rsync`
*   `dd`
*   `e2label`
*   `blkid`
*   `arch-chroot` (if you choose to chroot during installation)
*   `lsblk`
*   `hostnamectl`
*   `lscpu`
*   `free`


## Building from Source

The `obsidianctl` tool source code is modularized into several Python files and can be built into a single executable script using `make`.

1.  Clone the repository and `cd` into it.
2.  Run the `make` command to build the merged executable:
    ```bash
    make
    ```
    This will create a single executable file named `obsidianctl` in the current directory.
3. (Optional) Run the `make install` command as root to install the merged executable. It will install to `/usr/local/sbin`.

## Usage

You can run the `obsidianctl` script directly. Remember to run it with `sudo` as all commands other than `obsidianctl status` require root privileges.

```bash
sudo ./obsidianctl [command] [options]
```

### Commands

#### `status`

Displays the currently active A/B slot and various system details. This command does not require root.

```bash
./obsidianctl status
```

#### `install <device> <system_sfs>`

Partitions the specified device and installs the SquashFS system image. **WARNING: This will erase all data on the target device.**

*   `<device>`: The target block device (e.g., `/dev/sda`).
*   `<system_sfs>`: Path to the SquashFS system image file (e.g., `/path/to/obsidianos.sfs`). Defaults to `/etc/system.sfs`

```bash
sudo ./obsidianctl install /dev/sda /path/to/your_system.sfs
```

#### `switch <slot>`

Switches the active boot slot to either 'a' or 'b' for the next boot, persistently.

*   `<slot>`: The slot to make active (`a` or `b`).

```bash
sudo ./obsidianctl switch a
```

#### `switch-once <slot>`

Switches the active boot slot to either 'a' or 'b' once only.

*   `<slot>`: The slot to make active for once (`a` or `b`).

```bash
sudo ./obsidianctl switch-once a
```

#### `update <slot> <system_sfs>`

Updates a specific A/B slot with a new SquashFS system image. **WARNING: This will erase all data on the specified slot.**

*   `<slot>`: The slot to update (`a` or `b`).
*   `<system_sfs>`: Path to the new SquashFS system image file.

```bash
sudo ./obsidianctl update b /path/to/new_system_image.sfs
```

#### `sync <slot>`

Clones the currently running slot to the specified slot. This is a block-level copy using `dd`. It copies both the root and ESP partitions. **WARNING: This will erase all data on the specified slot.**

*   `<slot>`: The slot to sync to (`a` or `b`).

```bash
sudo ./obsidianctl sync b
```

#### `enter-slot <slot>`

Enters into a slot without rebooting. Uses `arch-chroot`.

*   `<slot>`: The slot to chroot into (`a` or `b`).
*   `--enable-networking`: Enables networking features.
*   `--mount-essentials`: Mounts /proc, /sys and /dev.
*   `--mount-home`: Mounts /home.
*   `--mount-root`: Mounts /root.

```bash
sudo ./obsidianctl enter-slot b --enable-networking --mount-home
```

#### `backup-slot <slot>`

Creates a compressed backup of a specific slot with metadata.

*   `<slot>`: The slot to backup (`a` or `b`).
*   `--backup-dir`: Directory to store backups (default: `/var/backups/obsidianctl/slot_X`).
*   `--device`: Drive (not partition) to backup (default: current drive).
*   `--full-backup`: Backup your ENTIRE SYSTEM. (EXPERIMENTAL. USE AT YOUR OWN RISK.)

```bash
sudo ./obsidianctl backup-slot a --backup-dir /mnt/external/backups
```

#### `rollback-slot <slot> <backup_path>`

Restores a slot from a previous backup.

*   `<slot>`: The slot to restore (`a` or `b`).
*   `<backup_path>`: Path to the backup file (`.sfs`).
*   `--device`: Drive (not partition) to rollback (default: current drive).

```bash
sudo ./obsidianctl rollback-slot a /var/backups/obsidianctl/slot_a/slot_a_backup_20250823_143022.sfs
```

#### `health-check`

Performs a comprehensive health assessment of both A/B slots.

```bash
sudo ./obsidianctl health-check
```

#### `verify-integrity <slot>`

Verifies filesystem integrity and checks for corrupted files in a specific slot.

*   `<slot>`: The slot to verify (`a` or `b`).

```bash
sudo ./obsidianctl verify-integrity a
```

#### `switch-kernel <kernel_name>`

Switches the default kernel that systemd-boot will use. This affects both slots unless a specific slot is provided.

*   `<kernel_name>`: The name of the kernel to switch to (e.g., `a` or `b`).
*   `--device <device>`: The target block device (e.g., `/dev/sda`). If not specified, the primary disk will be used.
*   `--slot <slot>`: The slot to modify (`a` or `b`). If not specified, both slots will be modified.

```bash
sudo ./obsidianctl switch-kernel a
sudo ./obsidianctl switch-kernel b --slot b
```

#### `ext`

Manages ObsidianOS extensions. Extensions are SquashFS images that can be mounted as overlays.

##### `ext add <path>`

Adds an ObsidianOS extension.

*   `<path>`: Path to the `.obsiext` file.

```bash
sudo ./obsidianctl ext add /path/to/my_extension.obsiext
```

##### `ext rm <name>`

Removes an ObsidianOS extension.

*   `<name>`: Name of the extension to remove.

```bash
sudo ./obsidianctl ext rm my_extension
```

##### `ext list`

Lists installed ObsidianOS extensions.

```bash
sudo ./obsidianctl ext list
```

##### `ext enable`

Enables ObsidianOS Overlays on boot. (Not implemented yet)

```bash
sudo ./obsidianctl ext enable
```

##### `ext disable`

Disables ObsidianOS Overlays on boot. (Not implemented yet)

```bash
sudo ./obsidianctl ext disable
```

## Modular Structure

The `obsidianctl` project is organized into a `modules` directory and a main `obsidianctl` file.

*   `modules/utils.py`: Contains common utility functions like `run_command`, `get_current_slot`, and `_get_part_path`. It also holds all necessary `import` statements for the entire script.
*   `modules/status.py`: Implements the `handle_status` command logic.
*   `modules/install.py`: Implements the `handle_install` command logic.
*   `modules/switch.py`: Implements the `handle_switch` command logic.
*   `modules/update.py`: Implements the `handle_update` command logic.
*   `modules/sync.py`: Implements the `handle_sync` command logic.
*   `modules/dualboot.py`: Handles dualbooting logic.
*   `modules/enter.py`: Implements entering slots.
*   `modules/backup.py`: Handles slot backup and rollback operations.
*   `modules/health.py`: Implements health checks and integrity verification.
*   `main`: Contains the main argument parsing logic and calls the appropriate handler functions.
*   `Makefile`: Orchestrates the concatenation of these files into a single executable script, ensuring proper shebang and import placement.

## License

[MIT](LICENSE)
