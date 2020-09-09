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
            if self.data:
                db_gateway.insert_document_section(db, "documentation", self.data, is_included)

    @dataclass()
    class CodeSectionInProgress:
        name: str
        data: str = ""

        def close(self, is_included):
            if self.data.endswith("\n"):
                self.data = self.data[:-1]
            db_gateway.insert_document_section(db, "code", self.data, is_included, self.name)

    def scan_file(path: Path, path_stack: Optional[List[Path]] = None):
        # Manage the stack of open files.
        is_included = path_stack is not None
        if path_stack is None:
            path_stack = []
        if path in path_stack:
            raise errors.FileIncludeRecursionError(f'The file "{path}" recursively includes itself.')
        path_stack.append(path)

        with open(path, "r") as f:
            current_section: Union[CodeSectionInProgress, DocumentationSectionInProgress] = DocumentationSectionInProgress()
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
    scan_file(source_document)


def assign_sequence_numbers_to_code_sections(ctx):
    db = db_gateway.get_database_connection(ctx)
    sequence_number = 1
    for code_section_id in db_gateway.code_section_ids_in_order(db):
        db_gateway.assign_code_section_sequence_number(db, code_section_id, sequence_number)
        sequence_number += 1


def split_document_sections_into_fragments(ctx):
    db = db_gateway.get_database_connection(ctx)
    for section_id, data in db_gateway.document_sections_in_order(db):
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
                db_gateway.insert_fragment(db, "plain text", section_id, plain_text)
            db_gateway.insert_fragment(db, "reference", section_id, reference_name, indent)
        if plain_text_start < len(data):
            db_gateway.insert_fragment(db, "plain text", section_id, data[plain_text_start:])


def resolve_all_abbreviations(ctx):
    def fix_abbreviations(find, fix):
        for id_to_fix, name in find(db):
            abbreviated_name = name[:-3]  # chop off the trailing '...'
            full_names = set(db_gateway.resolve_abbreviation(db, abbreviated_name))
            if (number_of_matches := len(full_names)) != 1:
                message = "does not identify any code-section."
                if number_of_matches > 1:
                    message = f"matches multiple code-sections -- {full_names}."
                raise errors.NonUniqueAbbreviationError(
                    f'The abbreviation "{name}" ' + message
                )
            fix(db, id_to_fix, full_names.pop())

    db = db_gateway.get_database_connection(ctx)
    db_gateway.collect_all_unabbreviated_names(db)
    fix_abbreviations(db_gateway.abbreviated_code_section_names, db_gateway.assign_code_section_name)
    fix_abbreviations(db_gateway.abbreviated_reference_fragment_names, db_gateway.assign_reference_fragment_name)


def group_fragments_by_section_name(ctx):
    db = db_gateway.get_database_connection(ctx)
    for name_id, name in db_gateway.unabbreviated_names(db):
        db_gateway.assign_fragment_name_ids(db, name_id, name)


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
    else:
        db_gateway.insert_non_root_name(db, name)
    if name in name_stack:
        raise errors.CodeSectionRecursionError(f'Code-section "{name}" recursively includes itself.')
    if not db_gateway.is_name_defined_by_code_section(db, name):
        raise errors.NoSuchCodeSectionError(f'Code-section "{name}" not found.')
    name_stack.append(name)

    document_section_separator = ""
    current_parent_document_section_id = None
    for (
            kind,
            parent_document_section_id,
            fragment_data,
            fragment_indent,
    ) in db_gateway.fragments_belonging_to_this_name_in_order(db, name):
        if parent_document_section_id != current_parent_document_section_id:
            hunk_in_progress += document_section_separator
            document_section_separator = "\n"
            current_parent_document_section_id = parent_document_section_id
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

    # Manage the stack of open code-section names.
    name_stack.pop()
    return hunk_in_progress


def resolve_named_code_sections_into_plain_text(ctx):
    db = db_gateway.get_database_connection(ctx)
    for root_name_id, root_name in db_gateway.unabbreviated_names(db, roots_only=True):
        # An output file should end with exactly one newline.
        code = assemble_fragments_into_plain_text(db, root_name).rstrip("\r\n") + "\n"
        db_gateway.insert_resolved_code_section(db, root_name_id, code)


def parse_source_file(ctx, db_path: str, root_source_file: Path):
    db_gateway.create_database(ctx, db_path)
    split_source_document_into_sections(ctx, root_source_file)
    assign_sequence_numbers_to_code_sections(ctx)
    split_document_sections_into_fragments(ctx)
    resolve_all_abbreviations(ctx)
    group_fragments_by_section_name(ctx)
    resolve_named_code_sections_into_plain_text(ctx)


def get_code_files(ctx):
    db = db_gateway.get_database_connection(ctx)
    return dict(db_gateway.resolved_code_sections(db))
