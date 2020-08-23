from reader import get_code_files
from writer import write_code_files

import click


@click.command()
@click.argument(
    "file_paths", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True), nargs=-1,
)
def tangle(file_paths):
    for file_path in file_paths:
        code_files = get_code_files(file_path)
        write_code_files(code_files)


if __name__ == "__main__":
    tangle()
