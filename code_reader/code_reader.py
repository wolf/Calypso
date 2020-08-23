from collections import defaultdict
from dataclasses import dataclass
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
CODE_BLOCK_REFERENCE = re.compile(r"(?:\n?([ \t]*))?(<<(.*)>>)")
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
    result: str, name: str, fragment_dict: Dict[str, Any], name_stack: Optional[List[str]] = None, indent: str = ""
) -> str:
    if name_stack is None:
        name_stack = []
    if name in name_stack:
        raise CodeSectionRecursionError(name)
    name_stack.append(name)
    if name not in fragment_dict:
        raise NoSuchCodeSectionError(name)
    for fragment in fragment_dict[name]:
        if isinstance(fragment, str):
            needs_indent = (len(name_stack) > 2) and result.endswith("\n")
            for line in fragment.splitlines(keepends=True):
                if needs_indent:
                    result += indent
                result += line
                needs_indent = True
        elif isinstance(fragment, CodeFragmentReference):
            result = assemble_fragments(result, fragment.name, fragment_dict, name_stack, indent + fragment.indent)
    name_stack.pop()
    return result


def build_output_files(fragment_dict, roots):
    output_files = {}
    for fragment_name in roots:
        fragment = assemble_fragments("", fragment_name, fragment_dict)
        if not fragment.endswith("\r\n"):
            fragment += "\n"
        output_files[fragment_name] = fragment
    return output_files


def get_code_files(file: Path):
    code_sections = split_source_file_into_code_sections(file)
    code_fragments, roots = split_code_sections_into_fragments(code_sections)
    return build_output_files(code_fragments, roots)
