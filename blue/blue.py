from pathlib import Path

import click

from blue.base.exceptions import CodeReaderError
from blue.bootstrap.code_reader import get_code_files
from blue.bootstrap.code_writer import write_code_files

@click.group()
@click.option("--debug/--no-debug", default=False)
@click.option("--verbose/--quiet", default=False)
@click.pass_context
def blue(ctx, debug, verbose):
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    ctx.obj["VERBOSE"] = verbose


@blue.command()
@click.option("--output", "-o", type=str, multiple=True)
@click.option("--base-dir", type=click.Path(file_okay=False, dir_okay=True, writable=True, readable=True))
@click.argument(
    "file_paths", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True), nargs=-1,
)
@click.pass_context
def tangle(ctx, output, file_paths, base_dir):
    if ctx.obj["VERBOSE"]:
        message = "tangling with debug turned on" if ctx.obj["DEBUG"] else "tangling"
        click.echo(message)
    roots_to_extract = set(output) or None
    for file_path in file_paths:
        try:
            code_files = get_code_files(ctx, Path(file_path))
            write_code_files(ctx, code_files, roots_to_extract, base_dir)
        except CodeReaderError as e:
            print(f'Error while processing "{file_path}": {e.message}')


@blue.command()
@click.pass_context
def weave(ctx):
    if ctx.obj["VERBOSE"]:
        message = "weaving with debug turned on" if ctx.obj["DEBUG"] else "weaving"
        click.echo(message)


if __name__ == "__main__":
    blue(obj={})
