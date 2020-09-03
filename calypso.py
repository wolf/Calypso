from pathlib import Path

import click

from calypso.base import CodeReaderError
from calypso.bootstrap.code_reader import get_code_files
from calypso.bootstrap.code_writer import write_code_files


@click.group()
def cli():
    pass


@cli.command()
@click.option("--output", "-o", type=str, multiple=True)
@click.option("--base-dir", type=click.Path(file_okay=False, dir_okay=True, writable=True, readable=True))
@click.argument(
    "file_paths", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True), nargs=-1,
)
def tangle(output, file_paths, base_dir):
    click.echo("tangling")
    roots_to_extract = set(output) or None
    for file_path in file_paths:
        try:
            code_files = get_code_files(Path(file_path))
            write_code_files(code_files, roots_to_extract, base_dir)
        except CodeReaderError as e:
            print(f'Error while processing "{file_path}": {e.message}')


@cli.command()
def weave():
    click.echo("weaving")


if __name__ == "__main__":
    cli()
