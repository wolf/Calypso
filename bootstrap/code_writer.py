import pathlib


def write_code_files(code_files):
    for file_name, code in code_files.items():
        path = pathlib.Path(file_name)
        owning_directory = path.parent
        if not owning_directory.exists():
            owning_directory.mkdir(parents=True)
        with open(path, "w") as f:
            f.write(code)
