from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Generator, List, Optional

import sqlite3
from sqlite3 import Connection, Cursor

import blue.base as base


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


@contextmanager
def open_cursor(db: Connection, writer: bool = False) -> Generator:
    cursor: Cursor = db.cursor()
    yield cursor
    if writer:
        db.commit()
    cursor.close()


class ParserState(Enum):
    NO_WORK_DONE_YET = 1
    DOCUMENT_SPLIT_INTO_SECTIONS = 2
    SEQUENCE_NUMBERS_ASSIGNED_TO_CODE_SECTIONS = 3
    SECTIONS_SPLIT_INTO_FRAGMENT_STREAMS = 4
    FULL_SECTION_NAMES_COLLECTED = 5
    ALL_ABBREVIATIONS_RESOLVED = 6
    FRAGMENT_STREAMS_GROUPED_BY_SECTION_NAME = 7
    ROOT_CODE_SECTIONS_RESOLVED_INTO_PLAIN_TEXT = 8


def get_parser_state(db: Connection) -> ParserState:
    with open_cursor(db) as parser_state_reader:
        parser_state_reader.execute("SELECT current_parser_state FROM parser_state WHERE id = 1")
        current_parser_state = parser_state_reader.fetchone()["current_parser_state"]
    return ParserState(current_parser_state)


def set_parser_state(db: Connection, new_parser_state: ParserState):
    with open_cursor(db, writer=True) as parser_state_writer:
        parser_state_writer.execute("""
            UPDATE parser_state SET current_parser_state = ? WHERE id = 1
        """, (new_parser_state.value,))


def create_database(ctx, db_path: str) -> Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = dict_factory
    ctx.obj["DATABASE_CONNECTION"] = db
    with open("blue/bootstrap/scanner_schema.sql") as f:
        sql_script = f.read()
    with open_cursor(db, writer=True) as database_writer:
        database_writer.executescript(sql_script)
    return db


def get_database_connection(ctx):
    return ctx.obj.get("DATABASE_CONNECTION", None)


def split_source_document_into_sections(ctx, source_document: Path):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.NO_WORK_DONE_YET

    insert_documentation_section = "INSERT INTO document_sections (kind, is_included, data) VALUES (1, ?, ?)"
    insert_code_section = "INSERT INTO document_sections (kind, is_included, name, data) VALUES (2, ?, ?, ?)"

    @dataclass()
    class DocumentationSectionInProgress:
        data: str = ""

        def close(self, db, is_included):
            if self.data:
                with open_cursor(db, writer=True) as section_writer:
                    section_writer.execute(insert_documentation_section, (1 if is_included else None, self.data))


    @dataclass()
    class CodeSectionInProgress:
        name: str
        data: str = ""

        def close(self, db, is_included):
            with open_cursor(db, writer=True) as section_writer:
                if self.data.endswith("\n"):
                    self.data = self.data[:-1]
                section_writer.execute(insert_code_section, (1 if is_included else None, self.name, self.data))


    def scan_file(path: Path, path_stack: Optional[List[Path]] = None):
        is_included = path_stack is not None
        if path_stack is None:
            path_stack = []
        if path in path_stack:
            raise base.FileIncludeRecursionError(f'The file "{path}" recursively includes itself.')
        path_stack.append(path)

        with open(path, "r") as f:
            current_section = DocumentationSectionInProgress()
            for line in f:
                if match := base.CODE_BLOCK_START_PATTERN.match(line):
                    current_section.close(db, is_included)
                    new_code_section_name = match.group(1).strip()
                    if not new_code_section_name:
                        raise base.BadSectionNameError(f"Code-section name must not be empty.")
                    if base.BAD_SECTION_NAME_PATTERN.search(new_code_section_name):
                        raise base.BadSectionNameError(
                            f'Code-section name "{new_code_section_name}" must not contain "<<" or ">>".'
                        )
                    current_section = CodeSectionInProgress(new_code_section_name)
                elif base.DOCUMENTATION_BLOCK_START_PATTERN.match(line):
                    current_section.close(db, is_included)
                    current_section = DocumentationSectionInProgress()
                elif match := base.INCLUDE_STATEMENT_PATTERN.match(line):
                    current_section.close(db, is_included)
                    relative_path = Path(match.group(1))
                    current_working_directory = path.parent
                    scan_file(current_working_directory / relative_path, path_stack)
                    current_section = DocumentationSectionInProgress()
                else:
                    current_section.data += line
            current_section.close(db, is_included)

        path_stack.pop()

    scan_file(source_document)
    set_parser_state(db, ParserState.DOCUMENT_SPLIT_INTO_SECTIONS)


def assign_sequence_numbers_to_code_sections(ctx):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.DOCUMENT_SPLIT_INTO_SECTIONS

    find_code_sections = "SELECT id FROM document_sections WHERE is_included IS NULL ORDER BY id"
    assign_sequence_number = "UPDATE document_sections SET code_section_sequence_number = ? WHERE id = ?"

    sequence_number = 1
    with open_cursor(db) as code_section_reader:
        for row in code_section_reader.execute(find_code_sections):
            with open_cursor(db, writer=True) as code_section_writer:
                code_section_writer.execute(assign_sequence_number, (sequence_number, row["id"]))
            sequence_number += 1

    set_parser_state(db, ParserState.SEQUENCE_NUMBERS_ASSIGNED_TO_CODE_SECTIONS)


def split_sections_into_fragment_streams(ctx):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.SEQUENCE_NUMBERS_ASSIGNED_TO_CODE_SECTIONS

    write_plain_text_fragment = "INSERT INTO fragments (kind, parent_document_section_id, data) VALUES (1, ?, ?)"
    write_reference_fragment = "INSERT INTO fragments (kind, parent_document_section_id, data, indent) VALUES (?, ?, ?, ?)"

    def add_plain_text_fragment(parent_section_id, text):
        with open_cursor(db, writer=True) as fragment_writer:
            fragment_writer.execute(write_plain_text_fragment, (parent_section_id, text))

    def add_reference_fragment(parent_section_id, is_escaped, name, indent):
        with open_cursor(db, writer=True) as fragment_writer:
            fragment_writer.execute(write_reference_fragment, (3 if is_escaped else 2, parent_section_id, name, indent))

    find_document_sections = "SELECT id, data FROM document_sections ORDER BY id"

    with open_cursor(db) as document_section_reader:
        document_section_reader.execute(find_document_sections)
        for row in document_section_reader.fetchall():
            section_id = row["id"]
            data = row["data"]
            plain_text_start = 0
            for match in base.CODE_BLOCK_REFERENCE_PATTERN.finditer(data):
                reference_is_escaped = False
                name = match.group("just_the_referenced_name").strip()
                if base.BAD_SECTION_NAME_PATTERN.search(name):
                    raise base.BadSectionNameError(f'Section name (reference) "{name}" must not contain "<<" or ">>".')
                indent = match.group("indent") or ""
                plain_text = data[plain_text_start : match.start("complete_reference")]
                if plain_text.endswith("\\"):
                    reference_is_escaped = True
                    plain_text = plain_text[:-1]
                plain_text_start = match.end("complete_reference")
                if plain_text:
                    add_plain_text_fragment(section_id, plain_text)
                add_reference_fragment(section_id, reference_is_escaped, name, indent)
            if plain_text_start < len(data):
                add_plain_text_fragment(section_id, data[plain_text_start:])

    set_parser_state(db, ParserState.SECTIONS_SPLIT_INTO_FRAGMENT_STREAMS)


def collect_full_section_names(ctx):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.SECTIONS_SPLIT_INTO_FRAGMENT_STREAMS

    find_code_section_names = "SELECT name FROM document_sections WHERE kind = 2 AND name NOT LIKE '%...'"
    find_reference_fragments = "SELECT data as name FROM fragments WHERE kind = 2 AND data NOT LIKE '%...'"
    write_names = "INSERT INTO code_section_full_names (name) VALUES (?)"

    full_section_names = set()
    with open_cursor(db) as code_section_reader:
        for row in code_section_reader.execute(find_code_section_names):
            full_section_names.add(row["name"])
    with open_cursor(db) as reference_fragment_reader:
        for row in reference_fragment_reader.execute(find_reference_fragments):
            full_section_names.add(row["name"])
    with open_cursor(db, writer=True) as name_writer:
        name_writer.executemany(write_names, [(name,) for name in full_section_names])
    set_parser_state(db, ParserState.FULL_SECTION_NAMES_COLLECTED)


def resolve_all_abbreviations(ctx):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.FULL_SECTION_NAMES_COLLECTED

    find_code_sections = "SELECT id, name FROM document_sections WHERE kind = 2 AND name LIKE '%...'"
    find_reference_fragments = "SELECT id, data as name FROM fragments WHERE kind = 2 AND data LIKE '%...'"
    fix_code_section = "UPDATE document_sections SET name = ? WHERE id = ?"
    fix_reference_fragment = "UPDATE fragments SET data = ? WHERE id = ?"
    find_full_name = "SELECT name FROM code_section_full_names WHERE name LIKE ?||'%'"

    def fix_abbreviations(find, fix):
        with open_cursor(db) as reader:
            for id, abbreviated_name in reader.execute(find):
                abbreviated_name = abbreviated_name[:-3]
                with open_cursor(db) as name_reader:
                    name_reader.execute(find_full_name, (abbreviated_name,))
                    full_name = name_reader.fetchone()["name"]
                    # TO DO: raise an error if full_names did not return exactly one row
                with open_cursor(db, writer=True) as writer:
                    writer.execute(fix, (full_name, id))

    fix_abbreviations(find_code_sections, fix_code_section)
    fix_abbreviations(find_reference_fragments, fix_reference_fragment)
    set_parser_state(db, ParserState.ALL_ABBREVIATIONS_RESOLVED)


def group_fragment_streams_by_section_name(ctx):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.ALL_ABBREVIATIONS_RESOLVED

    find_names = "SELECT id, name FROM code_section_full_names"
    group_fragment_streams = """
        UPDATE fragments SET code_section_name_id = ?
        WHERE parent_document_section_id IN (
            SELECT id FROM document_sections WHERE name = ?
        )
    """

    with open_cursor(db) as name_reader:
        for row in name_reader.execute(find_names):
            with open_cursor(db, writer=True) as fragment_writer:
                fragment_writer.execute(group_fragment_streams, (row["id"], row["name"]))
    set_parser_state(db, ParserState.FRAGMENT_STREAMS_GROUPED_BY_SECTION_NAME)


def resolve_named_code_sections_into_plain_text(ctx):

    insert_non_root_name = """
        INSERT OR IGNORE INTO non_root_code_sections (code_section_name_id)
        SELECT id FROM code_section_full_names WHERE name = ?
    """

    find_fragments_by_code_section_name = """
        SELECT
            description as kind,
            parent_document_section_id,
            data,
            indent
        FROM fragments
        LEFT JOIN fragment_kinds ON fragments.kind = fragment_kinds.id
        WHERE code_section_name_id = (
            SELECT id FROM code_section_full_names WHERE name = ?
        )
    """

    def name_is_a_non_root_code_section(name):
        with open_cursor(db, writer=True) as non_root_name_writer:
            non_root_name_writer.execute(insert_non_root_name, (name,))

    def coalesce_fragments(
            name: str,
            name_stack: Optional[List[str]] = None,
            hunk_in_progress: str = "",
            indent: str = "",
    ) -> str:
        nonlocal db

        if name_stack is None:
            name_stack = []
        else:
            name_is_a_non_root_code_section(name)
        if name in name_stack:
            raise base.CodeSectionRecursionError(f'Code-section "{name}" recursively includes itself.')
        name_stack.append(name)

        with open_cursor(db) as fragment_reader:
            document_section_separator = ""
            current_parent_document_section_id = None
            fragment_reader.execute(find_fragments_by_code_section_name, (name,))
            number_of_fragments = 0
            for row in fragment_reader.fetchall():
                number_of_fragments += 1
                if row["parent_document_section_id"] != current_parent_document_section_id:
                    hunk_in_progress += document_section_separator
                    document_section_separator = "\n"
                    current_parent_document_section_id = row["parent_document_section_id"]
                if row["kind"] == "plain text":
                    needs_indent = hunk_in_progress.endswith("\n")
                    for line in row["data"].splitlines(keepends=True):
                        if needs_indent:
                            hunk_in_progress += indent
                        hunk_in_progress += line
                        needs_indent = True
                elif row["kind"] == "reference":
                    hunk_in_progress = coalesce_fragments(
                        row["data"], name_stack, hunk_in_progress, indent + row["indent"]
                    )
                elif row["kind"] == "escaped reference":
                    hunk_in_progress += "<<" + row["data"] + ">>"
            if not number_of_fragments:
                raise base.NoSuchCodeSectionError(f'Code-section "{name}" not found.')

        name_stack.pop()
        return hunk_in_progress

    find_full_names = "SELECT name FROM code_section_full_names"

    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.FRAGMENT_STREAMS_GROUPED_BY_SECTION_NAME
    with open_cursor(db) as full_names_reader:
        full_names_reader.execute(find_full_names)
        all_names = {row["name"] for row in full_names_reader.fetchall()}

    insert_resolved_code_section = """
        INSERT OR IGNORE INTO resolved_code_sections (code_section_name_id, code) VALUES (?, ?)
    """

    delete_non_root_resolved_code_sections = """
        DELETE FROM resolved_code_sections WHERE code_section_name_id IN
        (SELECT code_section_name_id FROM non_root_code_sections)
    """

    get_full_name_id = "SELECT id FROM code_section_full_names WHERE name = ?"

    for name in all_names:
        with open_cursor(db, writer=True) as resolved_code_section_writer:
            code = coalesce_fragments(name).rstrip("\r\n") + "\n"
            with open_cursor(db) as full_name_reader:
                full_name_reader.execute(get_full_name_id, (name,))
                code_section_name_id = full_name_reader.fetchone()["id"]
            resolved_code_section_writer.execute(insert_resolved_code_section, (code_section_name_id, code))

    with open_cursor(db, writer=True) as resolved_code_section_writer:
        resolved_code_section_writer.execute(delete_non_root_resolved_code_sections)

    set_parser_state(db, ParserState.ROOT_CODE_SECTIONS_RESOLVED_INTO_PLAIN_TEXT)


def parse_source_file(ctx, db_path: str, root_source_file: Path):
    create_database(ctx, db_path)
    split_source_document_into_sections(ctx, root_source_file)
    assign_sequence_numbers_to_code_sections(ctx)
    split_sections_into_fragment_streams(ctx)
    collect_full_section_names(ctx)
    resolve_all_abbreviations(ctx)
    group_fragment_streams_by_section_name(ctx)
    resolve_named_code_sections_into_plain_text(ctx)


def get_code_files(ctx):
    db = get_database_connection(ctx)
    assert get_parser_state(db) == ParserState.ROOT_CODE_SECTIONS_RESOLVED_INTO_PLAIN_TEXT

    all_resolved_code_sections = """
        SELECT name, code
        FROM resolved_code_sections
        JOIN code_section_full_names ON code_section_name_id = id
    """

    code_files = {}
    with open_cursor(db) as resolved_code_section_reader:
        resolved_code_section_reader.execute(all_resolved_code_sections)
        for row in resolved_code_section_reader.fetchall():
            code_files[row["name"]] = row["code"]
    return code_files
