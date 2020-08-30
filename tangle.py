from pathlib import Path

from bootstrap.code_reader import get_code_files, CodeReaderError
from bootstrap.code_writer import write_code_files

import click


@click.command()
@click.option("--output", "-o", type=str, multiple=True)
@click.option("--base-dir", type=click.Path(file_okay=False, dir_okay=True, writable=True, readable=True))
@click.argument(
    "file_paths", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True), nargs=-1,
)
def tangle(output, file_paths, base_dir):
    roots_to_extract = set(output)
    for file_path in file_paths:
        try:
            code_files = get_code_files(Path(file_path))
            write_code_files(code_files, roots_to_extract, base_dir)
        except CodeReaderError as e:
            print(f'Error while processing "{file_path}": {e.message}')


if __name__ == "__main__":
    tangle()
