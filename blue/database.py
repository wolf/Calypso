from contextlib import contextmanager
from typing import Generator, Iterable

import sqlite3


@contextmanager
def open_cursor(db: sqlite3.Connection) -> Generator:
    cursor: sqlite3.Cursor = db.cursor()
    yield cursor
    cursor.close()


def get_database_connection(ctx):
    return ctx.obj.get("DATABASE_CONNECTION", None)


def set_database_connection(ctx, db: sqlite3.Connection):
    ctx.obj["DATABASE_CONNECTION"] = db


def create_database(ctx, db_path: str) -> sqlite3.Connection:
    db = sqlite3.connect(db_path, isolation_level=None)
    db.row_factory = sqlite3.Row
    set_database_connection(ctx, db)
    with open("blue/blue-schema.sql") as f:
        sql_script = f.read()
    with open_cursor(db) as database_writer:
        database_writer.executescript(sql_script)
    return db


def get_parser_state(db: sqlite3.Connection) -> int:
    sql = "SELECT current_parser_state FROM parser_state WHERE id = 1"
    with open_cursor(db) as parser_state_reader:
        parser_state_reader.execute(sql)
        return parser_state_reader.fetchone()["current_parser_state"]


def set_parser_state(db: sqlite3.Connection, new_parser_state: int):
    sql = "UPDATE parser_state SET current_parser_state = ? WHERE id = 1"
    with open_cursor(db) as parser_state_writer:
        parser_state_writer.execute(sql, (new_parser_state,))


def write_document_section(db: sqlite3.Connection, kind: str, data: str, is_included: bool, name: str = None):
    sql = """
        INSERT INTO document_sections (kind, is_included, name, data) VALUES (
            (SELECT id FROM document_section_kinds WHERE description = ?),
            ?, ?, ?
        )
    """
    with open_cursor(db) as section_writer:
        section_writer.execute(sql, (kind, int(is_included), name, data))


def read_document_sections(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT id, data FROM document_sections ORDER BY id
    """
    with open_cursor(db) as section_reader:
        for row in section_reader.execute(sql):
            yield row["id"], row["data"]


def search_for_code_section_ids(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT document_sections.id
        FROM document_sections
        INNER JOIN document_section_kinds ON document_sections.kind = document_section_kinds.id
        WHERE document_section_kinds.description = 'code'
            AND is_included = 0
    """
    with open_cursor(db) as code_section_reader:
        for row in code_section_reader.execute(sql):
            yield row["id"]


def read_resolved_code_sections(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT name, code
        FROM resolved_code_sections
        JOIN code_section_full_names ON code_section_name_id = id
    """
    with open_cursor(db) as code_section_reader:
        for row in code_section_reader.execute(sql):
            yield row


def write_resolved_code_section(db: sqlite3.Connection, code_section_name_id: int, code: str):
    sql = """
        INSERT OR IGNORE INTO resolved_code_sections (code_section_name_id, code) VALUES (?, ?)
    """
    with open_cursor(db) as resolved_code_section_writer:
        resolved_code_section_writer.execute(sql, (code_section_name_id, code))


def assign_code_section_sequence_number(db: sqlite3.Connection, code_section_id: int, sequence_number: int):
    sql = """
        UPDATE document_sections SET code_section_sequence_number = ? WHERE id = ?
    """
    with open_cursor(db) as code_section_writer:
        code_section_writer.execute(sql, (sequence_number, code_section_id))


def assign_code_section_name(db: sqlite3.Connection, code_section_id: int, name: str):
    sql = """
        UPDATE document_sections SET name = ? WHERE id = ?
    """
    with open_cursor(db) as code_section_writer:
        code_section_writer.execute(sql, (name, code_section_id))


def assign_fragment_name(db: sqlite3.Connection, fragment_id: int, name: str):
    sql = """
        UPDATE fragments SET data = ? WHERE id = ?
    """
    with open_cursor(db) as fragment_writer:
        fragment_writer.execute(sql, (name, fragment_id))


def write_fragment(db: sqlite3.Connection, kind: str, parent_document_section_id: int, data: str, indent: str = ""):
    sql = """
        INSERT INTO fragments (kind, parent_document_section_id, data, indent) VALUES (
            (SELECT id FROM fragment_kinds WHERE description = ?),
            ?, ?, ?
        )
    """
    with open_cursor(db) as fragment_writer:
        fragment_writer.execute(sql, (kind, parent_document_section_id, data, indent))


def search_for_unabbreviated_names(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT name
        FROM document_sections
        JOIN document_section_kinds ON document_sections.kind = document_section_kinds.id
        WHERE description = 'code'
            AND name NOT LIKE '%...'
        UNION
        SELECT data AS name
        FROM fragments
        JOIN fragment_kinds ON fragments.kind = fragment_kinds.id
        WHERE description = 'reference'
            AND data NOT LIKE '%...'
    """
    with open_cursor(db) as name_finder:
        for row in name_finder.execute(sql):
            yield row["name"]


def search_for_abbreviated_code_sections(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT document_sections.id, name
        FROM document_sections
        JOIN document_section_kinds ON document_sections.kind = document_section_kinds.id
        WHERE description = 'code'
            AND name LIKE '%...'
    """
    with open_cursor(db) as code_section_reader:
        for row in code_section_reader.execute(sql):
            yield row


def search_for_abbreviated_reference_fragments(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT fragments.id, data AS name
        FROM fragments
        JOIN fragment_kinds ON fragments.kind = fragment_kinds.id
        WHERE description = 'reference'
            AND data LIKE '%...'
    """
    with open_cursor(db) as fragment_reader:
        for row in fragment_reader.execute(sql):
            yield row


def write_unabbreviated_names(db: sqlite3.Connection, names: Iterable):
    sql = """
        INSERT OR IGNORE INTO code_section_full_names (name) VALUES (?)
    """
    with open_cursor(db) as name_writer:
        name_writer.executemany(sql, [(name,) for name in names])


def read_unabbreviated_names(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT id, name FROM code_section_full_names
    """
    with open_cursor(db) as name_reader:
        for row in name_reader.execute(sql):
            yield row["id"], row["name"]


def resolve_abbreviation(db: sqlite3.Connection, abbreviation: str) -> Generator:
    sql = """
        SELECT name FROM code_section_full_names WHERE name LIKE ?||'%'
    """
    with open_cursor(db) as name_reader:
        for row in name_reader.execute(sql, (abbreviation,)):
            yield row["name"]


def assign_fragment_name_ids(db: sqlite3.Connection, code_section_name_id: int, code_section_name: str):
    sql = """
        UPDATE fragments SET code_section_name_id = ?
        WHERE parent_document_section_id IN (
            SELECT id FROM document_sections WHERE name = ?
        )
    """
    with open_cursor(db) as fragment_writer:
        fragment_writer.execute(sql, (code_section_name_id, code_section_name))


def search_for_fragments_belonging_to_this_code_section(db: sqlite3.Connection, code_section_name: str) -> Generator:
    sql = """
        SELECT description AS kind,
            parent_document_section_id,
            data,
            indent
        FROM fragments
        JOIN fragment_kinds ON fragments.kind = fragment_kinds.id
        WHERE code_section_name_id = (
            SELECT id FROM code_section_full_names WHERE name = ?
        )
    """
    with open_cursor(db) as fragment_reader:
        for row in fragment_reader.execute(sql, (code_section_name,)):
            yield row


def write_non_root_name(db: sqlite3.Connection, name: str):
    sql = """
        INSERT OR IGNORE INTO non_root_code_sections (code_section_name_id)
        SELECT id FROM code_section_full_names WHERE name = ?
    """
    with open_cursor(db) as name_writer:
        name_writer.execute(sql, (name,))
