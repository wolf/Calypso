from pathlib import Path

from code_reader.code_reader import get_code_files
from code_writer.code_writer import write_code_files

import click


@click.command()
@click.argument(
    "file_paths", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True), nargs=-1,
)
def tangle(file_paths):
    for file_path in file_paths:
        code_files = get_code_files(Path(file_path))
        write_code_files(code_files)


if __name__ == "__main__":
    tangle()
