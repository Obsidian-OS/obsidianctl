
def handle_switch(args):
    slot = args.slot
    print(f"Switching active boot slot to '{slot}'...")

    boot_entries_raw = run_command("efibootmgr", capture_output=True, text=True).stdout
    boot_order_match = re.search(r"^BootOrder: (.*)$", boot_entries_raw, re.MULTILINE)
    if not boot_order_match:
        print("Could not determine boot order from efibootmgr.", file=sys.stderr)
        sys.exit(1)
    current_order = boot_order_match.group(1).split(",")

    slot_a_match = re.search(
        r"^Boot([0-9A-F]{4})\*?.*ObsidianOS \(Slot A\)", boot_entries_raw, re.MULTILINE
    )
    slot_b_match = re.search(
        r"^Boot([0-9A-F]{4})\*?.*ObsidianOS \(Slot B\)", boot_entries_raw, re.MULTILINE
    )
    slot_a_entry = slot_a_match.group(1) if slot_a_match else None
    slot_b_entry = slot_b_match.group(1) if slot_b_match else None
    if not slot_a_entry or not slot_b_entry:
        print(
            "Could not find boot entries for Slot A and Slot B. Was the system installed with obsidianctl?",
            file=sys.stderr,
        )
        sys.exit(1)
    new_order = list(current_order)
    target_entry = slot_a_entry if slot == "a" else slot_b_entry
    other_entry = slot_b_entry if slot == "a" else slot_a_entry
    if target_entry in new_order:
        new_order.remove(target_entry)
    if other_entry in new_order:
        new_order.remove(other_entry)

    new_order.insert(0, target_entry)
    new_order.insert(1, other_entry)
    final_order_str = ",".join(new_order)
    run_command(f"efibootmgr --bootorder {final_order_str}")
    print("Boot order updated.")
    run_command(f"efibootmgr -n {target_entry}")
    print(f"Next boot set to Slot {slot.upper()}. The change is persistent.")