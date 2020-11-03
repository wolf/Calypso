"""
Parse a literate source file into its components, and save them to an intermediate database that can be shared.

A literate source file is a sequence of sections.  Each section is either code or documentation.  One section ends when
another begins.  Code-sections start with a line that looks like this: `<<code-section name>>=` beginning in the
left-most column.  Documentation-sections begin with a single `@` character alone on a line (no white-space, and in the
left-most column).  The very first section is a documentation-section.  It needs no introduction.  Code and
documentation sections don't necessarily alternate.  Code-sections can immediately follow code-sections.  Likewise for
documentation.  Empty documentation-sections can be discarded.

The documentation-sections typically contain some kind of markup, e.g., Markdown, LaTeX, HTML, or even just plain text.
The code-sections can contain different languages.

The most important form of the source file, as it appears in the database, is as a collection of "fragments".  A
fragment is either one contiguous hunk of plain text (which might contain either code or documentation, or perhaps
something else in the future), or a reference to a named code-section.  In the latter case, the text of the fragment is
the name itself.  Fragments know from which document-section they came; and since document-sections know whether they
are code or documentation, you can tell what's in the fragment.  A fragment that belongs to a code-section also knows
the name (via an id) of that code.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import sqlite3

from blue import db_gateway, errors, patterns


def split_source_document_into_sections(ctx, source_document: Path):
    @dataclass()
    class DocumentationSectionInProgress:
        data: str = ""

        def close(self, is_included):
            nonlocal sequence
            if self.data:
                db_gateway.insert_document_section(db, "documentation", self.data, is_included, sequence=sequence)
                sequence += 1.0

    @dataclass()
    class CodeSectionInProgress:
        name: str
        data: str = ""

        def close(self, is_included):
            nonlocal sequence
            if self.data.endswith("\n"):
                self.data = self.data[:-1]
            db_gateway.insert_document_section(db, "code", self.data, is_included, self.name, sequence=sequence)
            sequence += 1.0

    def scan_file(path: Path, path_stack: Optional[List[Path]] = None):
        # Manage the stack of open files.
        is_included = path_stack is not None
        if path_stack is None:
            path_stack = []
        if path in path_stack:
            raise errors.FileIncludeRecursionError(f'The file "{path}" recursively includes itself.')
        path_stack.append(path)

        with open(path, "r") as f:
            current_section: Union[
                DocumentationSectionInProgress, CodeSectionInProgress
            ] = DocumentationSectionInProgress()
            for line in f:
                if match := patterns.CODE_BLOCK_START_PATTERN.match(line):
                    current_section.close(is_included)
                    new_code_section_name = match.group(1).strip()
                    if not new_code_section_name:
                        raise errors.BadSectionNameError(f"Code-section name must not be empty.")
                    if patterns.BAD_SECTION_NAME_PATTERN.search(new_code_section_name):
                        raise errors.BadSectionNameError(
                            f'Code-section name "{new_code_section_name}" must not contain "<<" or ">>".'
                        )
                    current_section = CodeSectionInProgress(new_code_section_name)
                elif patterns.DOCUMENTATION_BLOCK_START_PATTERN.match(line):
                    current_section.close(is_included)
                    current_section = DocumentationSectionInProgress()
                elif match := patterns.INCLUDE_STATEMENT_PATTERN.match(line):
                    current_section.close(is_included)
                    relative_path = Path(match.group(1))
                    current_working_directory = path.parent
                    scan_file(current_working_directory / relative_path, path_stack)
                    current_section = DocumentationSectionInProgress()
                else:
                    current_section.data += line
            current_section.close(is_included)

        # Manage the stack of open files.
        path_stack.pop()

    db = db_gateway.get_database_connection(ctx)
    sequence = 0.0
    scan_file(source_document)


def assign_presentation_numbers_to_code_sections(ctx):
    db = db_gateway.get_database_connection(ctx)
    for presentation_number, code_section_id in enumerate(db_gateway.code_section_ids_in_order(db), 1):
        db_gateway.assign_code_section_presentation_number(db, code_section_id, presentation_number)


def split_document_sections_into_fragments(ctx):
    db = db_gateway.get_database_connection(ctx)
    sequence = 0.0
    for section_id, data in db_gateway.raw_document_sections_in_order(db):
        plain_text_start = 0
        for match in patterns.CODE_BLOCK_REFERENCE_PATTERN.finditer(data):
            reference_name = match.group("just_the_referenced_name").strip()
            if patterns.BAD_SECTION_NAME_PATTERN.search(reference_name):
                raise errors.BadSectionNameError(
                    f'Section name (reference) "{reference_name}" must not contain "<<" or ">>".'
                )
            indent = match.group("indent") or ""
            plain_text = data[plain_text_start : match.start("complete_reference")]
            plain_text_start = match.end("complete_reference")
            if plain_text:
                db_gateway.insert_fragment(db, "plain text", section_id, plain_text, sequence=sequence)
                sequence += 1.0
            db_gateway.insert_fragment(db, "reference", section_id, reference_name, indent, sequence=sequence)
            sequence += 1.0
        if plain_text_start < len(data):
            db_gateway.insert_fragment(db, "plain text", section_id, data[plain_text_start:], sequence=sequence)
            sequence += 1.0


def resolve_all_abbreviations(ctx):
    def fix_abbreviations(find_fn, fix_fn):
        for id_to_fix, name in find_fn(db):
            abbreviated_name = name[:-3]  # chop off the trailing '...'
            full_names = set(db_gateway.resolve_abbreviation(db, abbreviated_name))
            if (number_of_matches := len(full_names)) != 1:
                message = "does not identify any code-section."
                if number_of_matches > 1:
                    message = f"matches multiple code-sections -- {full_names}."
                raise errors.NonUniqueAbbreviationError(f'The abbreviation "{name}" ' + message)
            fix_fn(db, id_to_fix, full_names.pop())

    db = db_gateway.get_database_connection(ctx)
    db_gateway.collect_all_unabbreviated_names(db)
    fix_abbreviations(db_gateway.abbreviated_code_section_names, db_gateway.assign_code_section_name)
    fix_abbreviations(db_gateway.abbreviated_reference_fragment_names, db_gateway.assign_reference_fragment_name)


def group_fragments_by_section_name(ctx):
    db = db_gateway.get_database_connection(ctx)
    for parent_name_id, name in db_gateway.unabbreviated_names(db):
        db_gateway.assign_fragment_parent_name_ids(db, parent_name_id, name)


def collect_non_root_names(ctx):
    db = db_gateway.get_database_connection(ctx)
    db_gateway.collect_non_root_names(db)


def assemble_fragments_into_plain_text(
    db: sqlite3.Connection,
    name: str,
    name_stack: Optional[List[str]] = None,
    hunk_in_progress: str = "",
    indent: str = "",
) -> str:

    # Manage the stack of open code-section names.
    if name_stack is None:
        name_stack = []
    if name in name_stack:
        raise errors.CodeSectionRecursionError(f'Code-section "{name}" recursively includes itself.')
    if not db_gateway.is_name_defined_by_code_section(db, name):
        raise errors.NoSuchCodeSectionError(f'Code-section "{name}" not found.')
    name_stack.append(name)

    document_section_separator = ""
    current_parent_id = None
    for (
        kind,
        parent_id,
        fragment_data,
        fragment_indent,
    ) in db_gateway.fragments_belonging_to_this_name_in_order(db, name):
        if parent_id != current_parent_id:
            hunk_in_progress += document_section_separator
            document_section_separator = "\n"
            current_parent_id = parent_id
        if kind == "plain text":
            needs_indent = hunk_in_progress.endswith("\n")
            for line in fragment_data.splitlines(keepends=True):
                if needs_indent:
                    hunk_in_progress += indent
                hunk_in_progress += line
                needs_indent = True
        elif kind == "reference":
            hunk_in_progress = assemble_fragments_into_plain_text(
                db, fragment_data, name_stack, hunk_in_progress, indent + fragment_indent
            )
        # TODO: raise an error if kind is something else?

    # Manage the stack of open code-section names.
    name_stack.pop()
    return hunk_in_progress


def resolve_named_code_sections_into_plain_text(ctx):
    db = db_gateway.get_database_connection(ctx)
    found_any_roots = False
    for root_name_id, root_name in db_gateway.unabbreviated_names(db, roots_only=True):
        # An output file should end with exactly one newline.
        code = assemble_fragments_into_plain_text(db, root_name).rstrip("\r\n") + "\n"
        db_gateway.insert_resolved_code(db, root_name_id, code)
        found_any_roots = True
    if not found_any_roots:
        raise errors.NoRootCodeSectionsFoundError("No root code sections found.")


def parse_source_file(ctx, db_path: str, root_source_file: Path):
    db_gateway.create_database(ctx, db_path)
    split_source_document_into_sections(ctx, root_source_file)
    assign_presentation_numbers_to_code_sections(ctx)
    split_document_sections_into_fragments(ctx)
    resolve_all_abbreviations(ctx)
    group_fragments_by_section_name(ctx)
    collect_non_root_names(ctx)
    resolve_named_code_sections_into_plain_text(ctx)


def get_code_files(ctx):
    db = db_gateway.get_database_connection(ctx)
    return dict(db_gateway.resolved_code(db))
