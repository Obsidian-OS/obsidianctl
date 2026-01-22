def enable_secureboot(arg):
    os.system(
        "sbctl create-keys || true"
        "sbctl sign-all || true"
    )

