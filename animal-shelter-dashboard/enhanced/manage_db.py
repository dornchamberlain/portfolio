# Run explicit database setup and CRUD commands from a local terminal.
import argparse
import json
from pathlib import Path
from shelter.config import Settings
from shelter.repository import RepositoryError
from shelter.sql_repository import SQLiteRepository


def main():
    parser = argparse.ArgumentParser(description="Manage the local shelter SQLite database")
    parser.add_argument("--database", type=Path, default=Settings.from_env({}).sqlite_file)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    load = commands.add_parser("import")
    load.add_argument("file", type=Path)
    create = commands.add_parser("create")
    create.add_argument("file", type=Path)
    change = commands.add_parser("update")
    change.add_argument("id")
    change.add_argument("file", type=Path)
    remove = commands.add_parser("delete")
    remove.add_argument("id")
    read = commands.add_parser("read")
    read.add_argument("--profile", default="RESET")
    read.add_argument("--page", type=int, default=0)
    read.add_argument("--page-size", type=int, default=10)
    read.add_argument("--animal-type")
    read.add_argument("--breed")
    args = parser.parse_args()
    repo = SQLiteRepository(args.database)
    try:
        if args.command == "init":
            repo.initialize()
            print("Schema is ready. Existing records were kept.")
        elif args.command in {"import", "create", "update"}:
            data = json.loads(args.file.read_text(encoding="utf-8"))
            if args.command == "import":
                if not isinstance(data, list):
                    raise ValueError("Import file must contain a JSON list.")
                print(f"Imported {repo.create_many(data)} records.")
            elif args.command == "create":
                print(f"Created {repo.create(data)}.")
            else:
                print("Updated." if repo.update(args.id, data) else "Record not found.")
        elif args.command == "delete":
            print("Deleted." if repo.delete(args.id) else "Record not found.")
        else:
            filters = {key: value for key, value in {"animal_type": args.animal_type, "breed": args.breed}.items() if value is not None}
            result = repo.read_page(profile=args.profile, filters=filters, page=args.page, page_size=args.page_size)
            print(json.dumps(vars(result), indent=2))
    except (RepositoryError, ValueError, OSError):
        # Keep file paths, submitted values, and database internals out of failure output.
        raise SystemExit("Operation failed. Check the input file, record constraints, and database setup.") from None
    finally:
        repo.close()


if __name__ == "__main__":
    main()
