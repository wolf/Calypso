from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from pathlib import Path
from typing import List, Optional, Union

import sqlite3

from blue import database, errors, patterns


@total_ordering
class ParserState(Enum):
    NO_WORK_DONE_YET = 1
    DOCUMENT_SPLIT_INTO_SECTIONS = 2
    SEQUENCE_NUMBERS_ASSIGNED_TO_CODE_SECTIONS = 3
    SECTIONS_SPLIT_INTO_FRAGMENT_STREAMS = 4
    FULL_SECTION_NAMES_COLLECTED = 5
    ALL_ABBREVIATIONS_RESOLVED = 6
    FRAGMENT_STREAMS_GROUPED_BY_SECTION_NAME = 7
    ROOT_CODE_SECTIONS_RESOLVED_INTO_PLAIN_TEXT = 8

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


def get_parser_state(db: sqlite3.Connection) -> ParserState:
    return ParserState(database.get_parser_state(db))


def set_parser_state(db: sqlite3.Connection, new_parser_state: ParserState):
    database.set_parser_state(db, new_parser_state.value)


def assert_parser_state(db: sqlite3.Connection, required_parser_state: ParserState):
    if get_parser_state(db) != required_parser_state:
        raise errors.ParsingTasksCalledOutOfSequence("Parsing task called out of sequence.")


def split_source_document_into_sections(ctx, source_document: Path):
    @dataclass()
    class DocumentationSectionInProgress:
        data: str = ""

        def close(self, is_included):
            if self.data:
                database.write_document_section(db, "documentation", self.data, is_included)

    @dataclass()
    class CodeSectionInProgress:
        name: str
        data: str = ""

        def close(self, is_included):
            if self.data.endswith("\n"):
                self.data = self.data[:-1]
            database.write_document_section(db, "code", self.data, is_included, self.name)

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

    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.NO_WORK_DONE_YET)
    scan_file(source_document)
    set_parser_state(db, ParserState.DOCUMENT_SPLIT_INTO_SECTIONS)


def assign_sequence_numbers_to_code_sections(ctx):
    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.DOCUMENT_SPLIT_INTO_SECTIONS)
    sequence_number = 1
    for code_section_id in database.search_for_code_section_ids_in_order(db):
        database.assign_code_section_sequence_number(db, code_section_id, sequence_number)
        sequence_number += 1
    set_parser_state(db, ParserState.SEQUENCE_NUMBERS_ASSIGNED_TO_CODE_SECTIONS)


def split_sections_into_fragment_streams(ctx):
    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.SEQUENCE_NUMBERS_ASSIGNED_TO_CODE_SECTIONS)
    for section_id, data in database.read_document_sections(db):
        plain_text_start = 0
        for match in patterns.CODE_BLOCK_REFERENCE_PATTERN.finditer(data):
            # TODO: I'm starting to think escaped references are a bad idea.  Think about this.
            reference_is_escaped = False
            reference_name = match.group("just_the_referenced_name").strip()
            if patterns.BAD_SECTION_NAME_PATTERN.search(reference_name):
                raise errors.BadSectionNameError(
                    f'Section name (reference) "{reference_name}" must not contain "<<" or ">>".'
                )
            indent = match.group("indent") or ""
            plain_text = data[plain_text_start : match.start("complete_reference")]
            if plain_text.endswith("\\"):
                reference_is_escaped = True
                plain_text = plain_text[:-1]  # chop off the escape character '\'
            plain_text_start = match.end("complete_reference")
            if plain_text:
                database.write_fragment(db, "plain text", section_id, plain_text)
            if reference_is_escaped:
                database.write_fragment(db, "escaped reference", section_id, reference_name)
            else:
                database.write_fragment(db, "reference", section_id, reference_name, indent)
        if plain_text_start < len(data):
            database.write_fragment(db, "plain text", section_id, data[plain_text_start:])
    set_parser_state(db, ParserState.SECTIONS_SPLIT_INTO_FRAGMENT_STREAMS)


def collect_full_section_names(ctx):
    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.SECTIONS_SPLIT_INTO_FRAGMENT_STREAMS)
    full_section_names = set(database.search_for_unabbreviated_names(db))
    database.write_many_unabbreviated_names(db, full_section_names)
    set_parser_state(db, ParserState.FULL_SECTION_NAMES_COLLECTED)


def resolve_all_abbreviations(ctx):
    def fix_abbreviations(find, fix):
        for id_to_fix, name in find(db):
            abbreviated_name = name[:-3]  # chop off the trailing '...'
            full_names = set(database.resolve_abbreviation(db, abbreviated_name))
            if (number_of_matches := len(full_names)) != 1:
                message = "does not identify any code-section."
                if number_of_matches > 1:
                    message = f"matches multiple code-sections -- {full_names}."
                raise errors.NonUniqueAbbreviationError(
                    f'The abbreviation "{name}" ' + message
                )
            fix(db, id_to_fix, full_names.pop())

    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.FULL_SECTION_NAMES_COLLECTED)
    fix_abbreviations(database.search_for_abbreviated_code_section_names, database.assign_code_section_name)
    fix_abbreviations(database.search_for_abbreviated_reference_fragment_names, database.assign_reference_fragment_name)
    set_parser_state(db, ParserState.ALL_ABBREVIATIONS_RESOLVED)


def group_fragment_streams_by_section_name(ctx):
    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.ALL_ABBREVIATIONS_RESOLVED)
    for name_id, name in database.read_unabbreviated_names(db):
        database.assign_fragment_name_ids(db, name_id, name)
    set_parser_state(db, ParserState.FRAGMENT_STREAMS_GROUPED_BY_SECTION_NAME)


def resolve_named_code_sections_into_plain_text(ctx):
    def coalesce_fragments(
        db_connection: sqlite3.Connection,
        name: str,
        name_stack: Optional[List[str]] = None,
        hunk_in_progress: str = "",
        indent: str = "",
    ) -> str:

        # Manage the stack of open code-section names.
        if name_stack is None:
            name_stack = []
        else:
            database.write_non_root_name(db_connection, name)
        if name in name_stack:
            raise errors.CodeSectionRecursionError(f'Code-section "{name}" recursively includes itself.')
        if not database.name_has_a_definition(db_connection, name):
            raise errors.NoSuchCodeSectionError(f'Code-section "{name}" not found.')
        name_stack.append(name)

        document_section_separator = ""
        current_parent_document_section_id = None
        for (
            kind,
            parent_document_section_id,
            fragment_data,
            fragment_indent,
        ) in database.search_for_fragments_belonging_to_this_name(db_connection, name):
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
                hunk_in_progress = coalesce_fragments(
                    db_connection, fragment_data, name_stack, hunk_in_progress, indent + fragment_indent
                )
            elif kind == "escaped reference":
                hunk_in_progress += "<<" + fragment_data + ">>"

        # Manage the stack of open code-section names.
        name_stack.pop()
        return hunk_in_progress

    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.FRAGMENT_STREAMS_GROUPED_BY_SECTION_NAME)
    for code_section_name_id, code_section_name in database.read_unabbreviated_names(db, root_code_sections_only=True):
        # An output file should end with exactly one newline.
        code = coalesce_fragments(db, code_section_name).rstrip("\r\n") + "\n"
        database.write_resolved_code_section(db, code_section_name_id, code)
    set_parser_state(db, ParserState.ROOT_CODE_SECTIONS_RESOLVED_INTO_PLAIN_TEXT)


def parse_source_file(ctx, db_path: str, root_source_file: Path):
    database.create_database(ctx, db_path)
    split_source_document_into_sections(ctx, root_source_file)
    assign_sequence_numbers_to_code_sections(ctx)
    split_sections_into_fragment_streams(ctx)
    collect_full_section_names(ctx)
    resolve_all_abbreviations(ctx)
    group_fragment_streams_by_section_name(ctx)
    resolve_named_code_sections_into_plain_text(ctx)


def get_code_files(ctx):
    db = database.get_database_connection(ctx)
    assert_parser_state(db, ParserState.ROOT_CODE_SECTIONS_RESOLVED_INTO_PLAIN_TEXT)
    return dict(database.read_resolved_code_sections(db))
