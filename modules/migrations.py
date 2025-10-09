def handle_migrate(args):
    checkroot()
    migration_id = str(args.id)
    repo_url = args.repo.format(id=migration_id)

    applied_migrations = get_applied_migrations()
    if migration_id in applied_migrations and not args.force:
        print(f"Migration {migration_id} already applied. Use --force to re-run.")
        return

    print(f"Fetching Migration #{migration_id}...")
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_script:
        temp_script_path = temp_script.name
        try:
            run_command(
                f'curl -fsSL -o {temp_script_path} {repo_url} -H "Cache-Control: no-cache"'
            )
        except Exception as e:
            print(f"Error: Failed to fetch migration script: {e}", file=sys.stderr)
            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)
            sys.exit(1)

    run_command(f"chmod +x {temp_script_path}")

    print(f"Running migration #{migration_id}...")
    env = os.environ.copy()
    env["CTLPATH"] = os.path.abspath(__file__)
    env["MIGRATION_ID"] = migration_id
    env["MIGRATION_REPO"] = repo_url

    try:
        run_command(f"bash {temp_script_path}", env=env)
        record_applied_migration(migration_id)
        print(f"Migration #{migration_id} completed successfully.")
    except Exception as e:
        print(f"Error: Migration {migration_id} failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        os.remove(temp_script_path)


def handle_rollback(args):
    checkroot()
    migration_id = str(args.id)
    repo_url = args.repo.format(id=migration_id)
    rollback_url = repo_url.replace(
        f"migration-{migration_id}.sh", f"migration-{migration_id}-rollback.sh"
    )

    applied_migrations = get_applied_migrations()
    if migration_id not in applied_migrations:
        print(
            f"Warning: Migration {migration_id} has not been applied, cannot roll back.",
            file=sys.stderr,
        )
        return

    print(
        f"Fetching rollback script for migration {migration_id} from {rollback_url}..."
    )

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_script:
        temp_script_path = temp_script.name
        try:
            run_command(f"curl -sSL -o {temp_script_path} {rollback_url}")
        except Exception as e:
            print(f"Error: Failed to fetch rollback script: {e}", file=sys.stderr)
            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)
            sys.exit(1)

    run_command(f"chmod +x {temp_script_path}")

    print(f"Running rollback script for migration {migration_id}...")
    env = os.environ.copy()
    env["CTLPATH"] = os.path.abspath(__file__)
    env["MIGRATION_ID"] = migration_id
    env["MIGRATION_REPO"] = repo_url

    try:
        run_command(f"bash {temp_script_path}", env=env)
        remove_applied_migration(migration_id)
        print(f"Rollback for migration {migration_id} completed successfully.")
    except Exception as e:
        print(
            f"Error: Rollback for migration {migration_id} failed: {e}", file=sys.stderr
        )
        sys.exit(1)
    finally:
        os.remove(temp_script_path)


def handle_list_migrations(args):
    checkroot()
    applied_migrations = get_applied_migrations()
    if not applied_migrations:
        print("No migrations have been applied yet.")
        return

    print("Applied Migrations:")
    for migration_id in applied_migrations:
        print(f"- {migration_id}")
