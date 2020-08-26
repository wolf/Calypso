import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


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


class CodeReaderError(RuntimeError):
    def __init__(self, message):
        self.message = message


class BadSectionNameError(CodeReaderError):
    pass


class CodeSectionRecursionError(CodeReaderError):
    pass


class NoSuchCodeSectionError(CodeReaderError):
    pass


class NoRootCodeSectionsFoundError(CodeReaderError):
    pass


class FileIncludeRecursionError(CodeReaderError):
    pass


DOCUMENTATION_BLOCK_START_PATTERN = re.compile(r"^@$")
CODE_BLOCK_START_PATTERN = re.compile(r"^<<(.*)>>=$")
CODE_BLOCK_REFERENCE_PATTERN = re.compile(r"(?:\n?([ \t]*))?(<<(.*?)>>)")
INCLUDE_STATEMENT_PATTERN = re.compile(r"^@include\((.*)\)$")
BAD_SECTION_NAME_PATTERN = re.compile(r"<<|>>")


def coalesce_code_sections(root_source_file: Path) -> Dict[str, str]:
    """
    For each unique code-section name in root_source_file and all its includes, build a hunk of text that is all the
    definitions of that name concatenated together in order.  Return a dictionary that maps each unique code-section
    name to its complete hunk of text.  Do this by maintaining a CodeSection object to accumulate the text of one
    section at a time.  It is None while we are not in a code-section.  The contents of the code-sections are not yet
    processed, so they will still contain references to other code-sections.
    """
    code_section: Optional[CodeSection] = None
    code_sections: Dict[str, str] = defaultdict(str)

    def close_code_section():
        """
        If we are collecting text from a code-section: stop collecting; and append it on to any previously collected
        code with the same name.
        """
        nonlocal code_section
        if code_section is not None:
            # code-sections are stored without a trailing newline
            if code_section.code.endswith("\n"):
                code_section.code = code_section.code[:-1]
            # concatenated code-sections start on a new line
            if code_section.name in code_sections:
                code_sections[code_section.name] += "\n"
            code_sections[code_section.name] += code_section.code
            code_section = None

    def scan_file(source_file: Path, path_stack: Optional[List[Path]] = None):
        """
        Scan through one source file, looking for code-sections.  Maintain a stack of open files so we don't get caught
        in a recursive loop.  Code sections are terminated by: (1) a new code-section start; (2) a documentation section
        start; (3) an include statement; or (4) the end of the file.
        """
        nonlocal code_section
        if path_stack is None:
            path_stack = []
        if source_file in path_stack:
            raise FileIncludeRecursionError(f'The file "{source_file}" recursively includes itself')
        path_stack.append(source_file)
        with open(source_file, "r") as f:
            for line in f:
                if match := CODE_BLOCK_START_PATTERN.match(line):
                    close_code_section()
                    new_code_section_name = match.group(1).strip()
                    if not new_code_section_name:
                        raise BadSectionNameError(f"section name must not be empty")
                    if BAD_SECTION_NAME_PATTERN.search(new_code_section_name):
                        raise BadSectionNameError(f'section name "{new_code_section_name}" may not contain "<<" or ">>"')
                    code_section = CodeSection(new_code_section_name)
                elif DOCUMENTATION_BLOCK_START_PATTERN.match(line):
                    close_code_section()
                elif match := INCLUDE_STATEMENT_PATTERN.match(line):
                    close_code_section()
                    relative_path = Path(match.group(1))
                    current_working_directory = source_file.parent
                    scan_file(current_working_directory / relative_path, path_stack)
                elif code_section:
                    code_section.code += line
            close_code_section()
        path_stack.pop()

    scan_file(root_source_file)
    return code_sections


def split_code_sections_into_fragments(code_section_dict: Dict[str, str]) -> Tuple[Dict[str, List[Any]], Set[str]]:
    """
    ...
    """
    fragment_dict = {}
    all_section_names = set()
    nonroots = set()
    for code_section_name, code_section in code_section_dict.items():
        all_section_names.add(code_section_name)
        fragment_list: List[Any] = []
        plain_code_start = 0
        for match in CODE_BLOCK_REFERENCE_PATTERN.finditer(code_section):
            name = match.group(3).strip()
            indent = match.group(1) or ""
            plain_code = code_section[plain_code_start:match.start(2)]
            plain_code_start = match.end(2)
            if plain_code:
                fragment_list.append(plain_code)
            fragment_list.append(CodeFragmentReference(name, indent))
            nonroots.add(name)
        if plain_code_start < len(code_section):
            fragment_list.append(code_section[plain_code_start:])
        fragment_dict[code_section_name] = fragment_list
    if all_section_names == nonroots:
        raise NoRootCodeSectionsFoundError("no root code-sections found")
    return fragment_dict, (all_section_names - nonroots)


def coalesce_fragments(
    result: str, name: str, fragment_dict: Dict[str, Any], name_stack: Optional[List[str]] = None, indent: str = ""
) -> str:
    if name_stack is None:
        name_stack = []
    if name in name_stack:
        raise CodeSectionRecursionError(f'code-section "{name}" recursively includes itself')
    name_stack.append(name)
    if name not in fragment_dict:
        raise NoSuchCodeSectionError(f'code-section "{name}" not found')
    for fragment in fragment_dict[name]:
        if isinstance(fragment, str):
            needs_indent = result.endswith("\n")
            for line in fragment.splitlines(keepends=True):
                if needs_indent:
                    result += indent
                result += line
                needs_indent = True
        elif isinstance(fragment, CodeFragmentReference):
            result = coalesce_fragments(result, fragment.name, fragment_dict, name_stack, indent + fragment.indent)
    name_stack.pop()
    return result


def build_output_files(fragment_dict, roots):
    output_files = {}
    for name in roots:
        output_files[name] = coalesce_fragments("", name, fragment_dict).rstrip("\r\n") + "\n"
    return output_files


def get_code_files(file: Path):
    code_sections = coalesce_code_sections(file)
    code_fragments, roots = split_code_sections_into_fragments(code_sections)
    return build_output_files(code_fragments, roots)
