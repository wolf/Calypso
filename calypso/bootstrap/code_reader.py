from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import calypso.base as base


@dataclass
class CodeSectionReference:
    name: str
    indent: str


def coalesce_code_sections(root_source_file: Path) -> Dict[str, str]:
    """
    For each unique code-section name in root_source_file and all its includes, build a hunk of text that is all the
    definitions of that name concatenated together in order.  Return a dictionary that maps each unique code-section
    name to its complete hunk of text.  Do this by maintaining a CodeSectionInProgress object to accumulate the text of
    one section at a time.  It is None while we are not in a code-section.  The contents of the code-sections are not
    yet processed, so they will still contain references to other code-sections.

    This function is called once per top-level source-file.
    """

    @dataclass
    class CodeSectionInProgress:
        name: str
        code: str

        def __init__(self, name):
            self.name = name
            self.code = ""

    code_section: Optional[CodeSectionInProgress] = None
    code_sections: Dict[str, str] = defaultdict(str)

    def close_code_section():
        """
        If we are collecting text from a code-section: stop collecting; and append it on to any previously collected
        code of the same name.

        This function is called after every possible code-section terminal boundary.
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
        in a recursive loop.  Code-sections are terminated by: (1) a new code-section start; (2) a documentation-section
        start; (3) an include statement; or (4) the end of the file.

        This function is called once per source-file.
        """
        nonlocal code_section

        # manage the stack of open file paths
        if path_stack is None:
            path_stack = []
        if source_file in path_stack:
            raise base.FileIncludeRecursionError(f'The file "{source_file}" recursively includes itself')
        path_stack.append(source_file)

        with open(source_file, "r") as f:
            for line in f:
                if match := base.CODE_BLOCK_START_PATTERN.match(line):
                    close_code_section()
                    new_code_section_name = match.group(1).strip()
                    if not new_code_section_name:
                        raise base.BadSectionNameError(f"section name must not be empty")
                    if base.BAD_SECTION_NAME_PATTERN.search(new_code_section_name):
                        raise base.BadSectionNameError(
                            f'section name "{new_code_section_name}" may not contain "<<" or ">>"'
                        )
                    code_section = CodeSectionInProgress(new_code_section_name)
                elif base.DOCUMENTATION_BLOCK_START_PATTERN.match(line):
                    close_code_section()
                elif match := base.INCLUDE_STATEMENT_PATTERN.match(line):
                    close_code_section()
                    relative_path = Path(match.group(1))
                    current_working_directory = source_file.parent
                    scan_file(current_working_directory / relative_path, path_stack)
                elif code_section is not None:
                    code_section.code += line
            # eof also closes an open code-section
            close_code_section()

        # manage the stack of open file paths
        path_stack.pop()

    scan_file(root_source_file)
    return code_sections


def split_code_sections_into_fragment_lists(code_section_dict: Dict[str, str]) -> Tuple[Dict[str, List[Any]], Set[str]]:
    """
    A code-section starts life as a single hunk of text (a str) containing embedded references to other code-sections.
    In the final output, each of these embedded references must be replaced with the code it references.  Since code-
    sections can be referenced more than once (and with different indents) we can't just expand everything in a single
    pass.  So we do it in two steps.  This function is the first step, where we convert every named code-section into a
    corresponding named fragment-list: a dict->dict transformation.

    A fragment-list is an ordered sequence of two different kinds of objects: (1) a plain hunks of code, represented by
    str's; and (2) references to named code-sections, represented by a CodeSectionReference's.  The two types do not
    necessarily alternate.  While we're looking for references, we're skipping over plain code.  Keep track of where
    that plain code starts (the end of the last reference we collected) so we can turn that into a fragment in the list
    when we stop to collect the next reference.

    Since we see every code-section name and notice if it is ever included, we can also build a set of root names.  We
    return both the dictionary of named fragment-lists and the set of root names.
    """
    fragment_dict = {}
    all_section_names = set()
    referenced_section_names = set()
    for code_section_name, code_section in code_section_dict.items():
        all_section_names.add(code_section_name)
        fragment_list: List[Any] = []
        plain_code_start = 0
        for match in base.CODE_BLOCK_REFERENCE_PATTERN.finditer(code_section):
            reference_is_escaped = False
            name = match.group("just_the_referenced_name").strip()
            if base.BAD_SECTION_NAME_PATTERN.search(name):
                raise base.BadSectionNameError(f'section name (reference) "{name}" may not contain "<<" or ">>"')
            indent = match.group("indent") or ""
            plain_code = code_section[plain_code_start : match.start("complete_reference")]
            if plain_code.endswith("\\"):
                reference_is_escaped = True
                # chop off the escape character and collect the reference as plain code
                plain_code = plain_code[:-1]
                plain_code_start = match.start("complete_reference")
            else:
                # else the next hunk of plain code starts immediately after the reference we are currently collecting
                plain_code_start = match.end("complete_reference")
            if plain_code:
                fragment_list.append(plain_code)
            if not reference_is_escaped:
                fragment_list.append(CodeSectionReference(name, indent))
                referenced_section_names.add(name)
        # if there's any un-collected plain code at the end: collect it
        if plain_code_start < len(code_section):
            fragment_list.append(code_section[plain_code_start:])
        fragment_dict[code_section_name] = fragment_list
    roots = all_section_names - referenced_section_names
    if not roots:
        raise base.NoRootCodeSectionsFoundError("no root code-sections found")
    return fragment_dict, roots


def coalesce_fragments(
    hunk_in_progress: str,
    name: str,
    fragment_dict: Dict[str, List[Any]],
    name_stack: Optional[List[str]] = None,
    indent: str = "",
) -> str:
    """
    Recursively step through a list of text fragments and references to other named lists of fragments and assemble them
    into contiguous hunks of text, being careful to preserve correct indentation.  Return that contiguous hunk of text.
    Maintain a stack of open section-names as we are referencing them to prevent getting caught in a recursive loop.

    This function is called once for each root code-section definition, and once for each reference to a named code-
    section.
    """
    # manage the stack of open code-section names
    if name_stack is None:
        name_stack = []
    if name in name_stack:
        raise base.CodeSectionRecursionError(f'code-section "{name}" recursively includes itself')
    name_stack.append(name)

    if name not in fragment_dict:
        raise base.NoSuchCodeSectionError(f'code-section "{name}" not found')
    for fragment in fragment_dict[name]:
        if isinstance(fragment, str):
            needs_indent = hunk_in_progress.endswith("\n")
            for line in fragment.splitlines(keepends=True):
                if needs_indent:
                    hunk_in_progress += indent
                hunk_in_progress += line
                needs_indent = True
        elif isinstance(fragment, CodeSectionReference):
            hunk_in_progress = coalesce_fragments(
                hunk_in_progress, fragment.name, fragment_dict, name_stack, indent + fragment.indent
            )

    # manage the stack of open code-section names
    name_stack.pop()

    return hunk_in_progress


def get_code_files(root_source_file: Path) -> Dict[str, str]:
    """
    Pull together all the steps provided above to create complete hunks of text corresponding to output files.  Could
    have replaced the last four lines with a dictionary comprehension, but this is clearer.

    This function is called once per top-level source file.
    """
    code_sections: Dict[str, str] = coalesce_code_sections(root_source_file)
    fragment_lists, roots = split_code_sections_into_fragment_lists(code_sections)
    output_files: Dict[str, str] = {}
    for root in roots:
        # an output file should end with exactly one newline
        output_files[root] = coalesce_fragments("", root, fragment_lists).rstrip("\r\n") + "\n"
    return output_files
