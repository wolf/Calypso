from pathlib import Path


def write_code_files(ctx, code_files, roots_to_extract=None, base_directory=None):
    base_directory = Path('.') if base_directory is None else Path(base_directory)
    for file_name, code in code_files.items():
        if roots_to_extract is not None and file_name not in roots_to_extract:
            continue
        path = base_directory / file_name
        owning_directory = path.parent
        if not owning_directory.exists():
            owning_directory.mkdir(parents=True)
        with open(path, "w") as f:
            f.write(code)
