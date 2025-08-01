# obsidianctl

`obsidianctl` is a command-line utility designed to manage A/B boot slots and shared partitions on ObsidianOS systems. It provides functionalities for system installation, status monitoring, active slot switching, and updating system images.

## Features

*   **`status`**: Display current active A/B slot and detailed system information in a neofetch-like format.
*   **`install`**: Partition a target device and install a SquashFS system image onto both A and B slots, setting up shared `/etc`, `/var`, and `/home` partitions, and configuring UEFI boot entries.
*   **`switch`**: Change the active boot slot (A or B) for the next boot, persistently.
*   **`update`**: Update a specific A/B slot with a new SquashFS system image.

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

## Usage

You can run the `obsidianctl` script directly. Remember to run it with `sudo` as it requires root privileges.

```bash
sudo ./obsidianctl [command] [options]
```

### Commands

#### `status`

Displays the currently active A/B slot and various system details.

```bash
sudo ./obsidianctl status
```

#### `install <device> <system_sfs>`

Partitions the specified device and installs the SquashFS system image. **WARNING: This will erase all data on the target device.**

*   `<device>`: The target block device (e.g., `/dev/sda`).
*   `<system_sfs>`: Path to the SquashFS system image file (e.g., `/path/to/archlinux.sfs`).

```bash
sudo ./obsidianctl install /dev/sda /path/to/your_system.sfs
```

#### `switch <slot>`

Switches the active boot slot to either 'a' or 'b'. This change is persistent across reboots.

*   `<slot>`: The slot to make active (`a` or `b`).

```bash
sudo ./obsidianctl switch a
```

#### `update <slot> <system_sfs>`

Updates a specific A/B slot with a new SquashFS system image. **WARNING: This will erase all data on the specified slot.**

*   `<slot>`: The slot to update (`a` or `b`).
*   `<system_sfs>`: Path to the new SquashFS system image file.

```bash
sudo ./obsidianctl update b /path/to/new_system_image.sfs
```

## Modular Structure

The `obsidianctl` project is organized into a `modules` directory and a main `obsidianctl` file.

*   `modules/utils.py`: Contains common utility functions like `run_command`, `get_current_slot`, and `_get_part_path`. It also holds all necessary `import` statements for the entire script.
*   `modules/status.py`: Implements the `handle_status` command logic.
*   `modules/install.py`: Implements the `handle_install` command logic.
*   `modules/switch.py`: Implements the `handle_switch` command logic.
*   `modules/update.py`: Implements the `handle_update` command logic.
*   `obsidianctl`: Contains the main argument parsing logic and calls the appropriate handler functions.
*   `Makefile`: Orchestrates the concatenation of these files into a single executable script, ensuring proper shebang and import placement.

## License

[MIT](LICENSE)
