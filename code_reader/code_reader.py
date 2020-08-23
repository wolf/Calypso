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
class CodeSection:
    name: str
    code: str

    def __init__(self, name):
        self.name = name
        self.code = ""


class CodeSectionRecursionError(RuntimeError):
    pass


class NoSuchCodeSectionError(KeyError):
    pass


class NoRootCodeSectionsFound(RuntimeError):
    pass


CODE_BLOCK_START_PATTERN = re.compile(r"^<<(.*)>>=$")
CODE_BLOCK_REFERENCE = re.compile(r"(?:\n([ \t]+))?(<<(.*)>>)")
INCLUDE_STATEMENT_PATTERN = re.compile(r"^@include\((.*)\)$")
DOCUMENTATION_BLOCK_START_PATTERN = re.compile(r"^@$")


def split_source_file_into_code_sections(file: Path) -> Dict[str, str]:
    code_section: Optional[CodeSection] = None
    code_sections: Dict[str, str] = defaultdict(str)

    def close_section():
        nonlocal code_section
        if code_section is not None:
            if code_section.name in code_sections:
                code_sections[code_section.name] += "\n"
            code_sections[code_section.name] += code_section.code.rstrip("\r\n")
            code_section = None

    def scan_file(file: Path):
        nonlocal code_section
        with open(file, "r") as f:
            for line in f:
                if match := CODE_BLOCK_START_PATTERN.match(line):
                    close_section()
                    code_section = CodeSection(match.group(1))
                elif DOCUMENTATION_BLOCK_START_PATTERN.match(line):
                    close_section()
                elif (match := INCLUDE_STATEMENT_PATTERN.match(line)) and not code_section:
                    relative_path = Path(match.group(1))
                    current_working_directory = file.parent
                    scan_file(current_working_directory / relative_path)
                elif code_section:
                    code_section.code += line
            close_section()

    scan_file(file)
    return code_sections


def split_code_sections_into_fragments(code_section_dict: Dict[str, str]):
    fragment_dict = {}
    all_section_names = set()
    nonroots = set()
    for code_section_name, code_section in code_section_dict.items():
        all_section_names.add(code_section_name)
        fragment_list = []
        plain_code_start = 0
        for match in CODE_BLOCK_REFERENCE.finditer(code_section):
            name = match.group(3)
            indent = match.group(1) or ""
            plain_code = code_section[plain_code_start : match.start(2)]
            plain_code_start = match.end(2)
            if plain_code:
                fragment_list.append(plain_code)
            fragment_list.append(CodeFragmentReference(name, indent))
            nonroots.add(name)
        if plain_code_start < len(code_section):
            fragment_list.append(code_section[plain_code_start:])
        fragment_dict[code_section_name] = fragment_list
    if all_section_names == nonroots:
        raise NoRootCodeSectionsFound()
    return fragment_dict, (all_section_names - nonroots)


def assemble_fragments(
    stream: Optional[StringIO],
    fragment_name: str,
    fragments: Dict[str, Any],
    fragment_name_stack: Optional[List[str]] = None,
    indent: str = ""
):
    if fragment_name_stack is None:
        fragment_name_stack = []
    if fragment_name in fragment_name_stack:
        raise CodeSectionRecursionError(fragment_name)
    fragment_name_stack.append(fragment_name)
    if fragment_name not in fragments:
        raise NoSuchCodeSectionError(fragment_name)
    for fragment in fragments[fragment_name]:
        if isinstance(fragment, str):
            for line in fragment.splitlines(keepends=True):
                stream.write(indent + line)
        elif isinstance(fragment, CodeFragmentReference):
            assemble_fragments(
                stream, fragment.name, fragments, fragment_name_stack, indent + fragment.indent
            )
    fragment_name_stack.pop()


def build_output_files(fragment_dict, roots):
    output_files = {}
    for fragment_name in roots:
        stream = StringIO("")
        assemble_fragments(stream, fragment_name, fragment_dict)
        if not stream.getvalue().endswith("\r\n"):
            stream.write("\n")
        output_files[fragment_name] = stream.getvalue()
    return output_files


def get_code_files(file: Path):
    code_sections = split_source_file_into_code_sections(file)
    code_fragments, roots = split_code_sections_into_fragments(code_sections)
    return build_output_files(code_fragments, roots)
