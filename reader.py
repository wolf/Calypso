from collections import defaultdict
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import re
from typing import Dict, Optional, Any, List


@dataclass
class CodeFragmentReference:
    name: str
    indent: str


@dataclass
class CodeBlock:
    name: str
    code: str

    def __init__(self, name):
        self.name = name
        self.code = ""


class CodeBlockRecursionError(RuntimeError):
    pass


class NoSuchCodeBlockError(KeyError):
    pass


CODE_BLOCK_START_PATTERN = re.compile(r"^<<(.*)>>=$")
CODE_BLOCK_REFERENCE = re.compile(r"(?:\n([ \t]+))?(<<(.*)>>)")
DOCUMENTATION_START_PATTERN = re.compile(r"^@$")


def split_source_file_into_code_blocks(file: Path):
    """..."""

    def close_block():
        nonlocal code_block
        if code_block is not None:
            if code_block.name in code_blocks:
                code_blocks[code_block.name] += "\n"
            code_blocks[code_block.name] += code_block.code.rstrip("\r\n")
            code_block = None

    code_blocks = defaultdict(str)
    code_block = None
    with open(file, "r") as f:
        for line in f:
            if (match := CODE_BLOCK_START_PATTERN.match(line)) is not None:
                close_block()
                code_block = CodeBlock(match.group(1))
            elif DOCUMENTATION_START_PATTERN.match(line):
                close_block()
            elif code_block is not None:
                code_block.code += line
    return code_blocks


def split_code_blocks_into_fragments(code_block_dict: Dict[str, str]):
    fragment_dict = {}
    all_block_names = set()
    nonroots = set()
    for code_block_name, code_block in code_block_dict.items():
        all_block_names.add(code_block_name)
        fragment_list = []
        plain_code_start = 0
        for match in CODE_BLOCK_REFERENCE.finditer(code_block):
            name = match.group(3)
            indent = match.group(1) or ""
            plain_code = code_block[plain_code_start : match.start(2)]
            plain_code_start = match.end(2)
            if plain_code:
                fragment_list.append(plain_code)
            fragment_list.append(CodeFragmentReference(name, indent))
            nonroots.add(name)
        if plain_code_start < len(code_block):
            fragment_list.append(code_block[plain_code_start:])
        fragment_dict[code_block_name] = fragment_list
    if all_block_names == nonroots:
        raise CodeBlockRecursionError()
    return fragment_dict, all_block_names - nonroots


def assemble_fragments(
    stream: Optional[StringIO],
    fragment_name: str,
    fragments: Dict[str, Any],
    fragment_name_stack: Optional[List[str]] = None,
    indent="",
    fragment_indent="",
):
    if fragment_name_stack is None:
        fragment_name_stack = []
    if fragment_name in fragment_name_stack:
        raise CodeBlockRecursionError(fragment_name)
    fragment_name_stack.append(fragment_name)
    if fragment_name not in fragments:
        raise NoSuchCodeBlockError(fragment_name)
    for fragment in fragments[fragment_name]:
        if isinstance(fragment, str):
            actual_indent = indent
            for line in fragment.splitlines(keepends=True):
                stream.write(actual_indent + line)
                actual_indent = indent + fragment_indent
        elif isinstance(fragment, CodeFragmentReference):
            assemble_fragments(
                stream, fragment.name, fragments, fragment_name_stack, indent, fragment.indent,
            )
    fragment_name_stack.pop()


def build_output_files(fragment_dict, roots):
    output_files = {}
    for fragment_name in roots:
        stream = StringIO("")
        assemble_fragments(stream, fragment_name, fragment_dict)
        output_files[fragment_name] = stream.getvalue()
    return output_files


def get_code_files(file: Path):
    code_blocks = split_source_file_into_code_blocks(file)
    code_fragments, roots = split_code_blocks_into_fragments(code_blocks)
    return build_output_files(code_fragments, roots)
