from contextlib import contextmanager
from typing import Generator, Iterable, Optional

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
    db.executescript(sql_script)
    return db


def insert_document_section(db: sqlite3.Connection, kind: str, data: str, is_included: bool, name: Optional[str] = None):
    sql = """
        INSERT INTO document_sections (kind_id, is_included, name, data) VALUES (
            (SELECT id FROM document_section_kinds WHERE description = ?),
            ?, ?, ?
        )
    """
    db.execute(sql, (kind, int(is_included), name, data))


def document_sections_in_order(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT id, data FROM document_sections ORDER BY id
    """
    for row in db.execute(sql):
        yield row


def code_section_ids_in_order(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT document_sections.id
        FROM document_sections
        JOIN document_section_kinds ON document_sections.kind_id = document_section_kinds.id
        WHERE document_section_kinds.description = 'code'
            AND is_included = 0
        ORDER BY document_sections.id
    """
    for row in db.execute(sql):
        yield row["id"]


def resolved_code_sections(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT name, code
        FROM resolved_code_sections
        JOIN code_section_full_names ON code_section_name_id = id
    """
    for row in db.execute(sql):
        yield row


def insert_resolved_code_section(db: sqlite3.Connection, code_section_name_id: int, code: str):
    sql = """
        INSERT OR IGNORE INTO resolved_code_sections (code_section_name_id, code) VALUES (?, ?)
    """
    db.execute(sql, (code_section_name_id, code))


def assign_code_section_sequence_number(db: sqlite3.Connection, code_section_id: int, sequence_number: int):
    sql = """
        UPDATE document_sections SET code_section_sequence_number = ? WHERE id = ?
    """
    db.execute(sql, (sequence_number, code_section_id))


def assign_code_section_name(db: sqlite3.Connection, code_section_id: int, name: str):
    sql = """
        UPDATE document_sections SET name = ? WHERE id = ?
    """
    db.execute(sql, (name, code_section_id))


def assign_reference_fragment_name(db: sqlite3.Connection, fragment_id: int, name: str):
    sql = """
        UPDATE fragments SET data = ? WHERE id = ?
    """
    db.execute(sql, (name, fragment_id))


def insert_fragment(db: sqlite3.Connection, kind: str, parent_document_section_id: int, data: str, indent: str = ""):
    sql = """
        INSERT INTO fragments (kind_id, parent_document_section_id, data, indent) VALUES (
            (SELECT id FROM fragment_kinds WHERE description = ?),
            ?, ?, ?
        )
    """
    db.execute(sql, (kind, parent_document_section_id, data, indent))


def collect_all_unabbreviated_names(db: sqlite3.Connection):
    """
    Search among code-sections for those with unabbreviated names; then search among reference fragments for those whose
    references are unabbreviated.  Save the found names in the code_sections_full_names table.

    I would try to enforce order here so that the first found unabbreviated name then becomes the canonical version with
    respect to capitalization; but that turns out to be hard to do in SQL.
    """

    sql = """
        INSERT OR IGNORE INTO code_section_full_names (name)
        SELECT name
        FROM document_sections
        JOIN document_section_kinds ON document_sections.kind_id = document_section_kinds.id
        WHERE description = 'code'
            AND name NOT LIKE '%...'
        UNION
        SELECT data AS name
        FROM fragments
        JOIN fragment_kinds ON fragments.kind_id = fragment_kinds.id
        WHERE description = 'reference'
            AND data NOT LIKE '%...'
    """
    db.execute(sql)


def abbreviated_code_section_names(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT document_sections.id, name
        FROM document_sections
        JOIN document_section_kinds ON document_sections.kind_id = document_section_kinds.id
        WHERE description = 'code'
            AND name LIKE '%...'
    """
    for row in db.execute(sql):
        yield row


def abbreviated_reference_fragment_names(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT fragments.id, data AS name
        FROM fragments
        JOIN fragment_kinds ON fragments.kind_id = fragment_kinds.id
        WHERE description = 'reference'
            AND data LIKE '%...'
    """
    for row in db.execute(sql):
        yield row


def unabbreviated_names(db: sqlite3.Connection, roots_only: bool = False) -> Generator:
    sql = """
        SELECT id, name FROM code_section_full_names
    """
    if roots_only:
        sql += """
            EXCEPT
            SELECT id, name FROM non_root_code_sections
            JOIN code_section_full_names ON code_section_full_names.id = code_section_name_id
        """
    for row in db.execute(sql):
        yield row


def resolve_abbreviation(db: sqlite3.Connection, abbreviation: str) -> Generator:
    sql = """
        SELECT name FROM code_section_full_names WHERE name LIKE ?||'%'
    """
    for row in db.execute(sql, (abbreviation,)):
        yield row["name"]


def assign_fragment_name_ids(db: sqlite3.Connection, code_section_name_id: int, code_section_name: str):
    sql = """
        UPDATE fragments SET code_section_name_id = ?
        WHERE parent_document_section_id IN (
            SELECT id FROM document_sections WHERE name = ?
        )
    """
    db.execute(sql, (code_section_name_id, code_section_name))


def fragments_belonging_to_this_name_in_order(db: sqlite3.Connection, code_section_name: str) -> Generator:
    sql = """
        SELECT
            description AS kind,
            parent_document_section_id,
            data,
            indent
        FROM fragments
        JOIN fragment_kinds ON fragments.kind_id = fragment_kinds.id
        WHERE code_section_name_id = (
            SELECT id FROM code_section_full_names WHERE name = ?
        )
        ORDER BY parent_document_section_id, fragments.id
    """
    for row in db.execute(sql, (code_section_name,)):
        yield row


def insert_non_root_name(db: sqlite3.Connection, name: str):
    sql = """
        INSERT OR IGNORE INTO non_root_code_sections (code_section_name_id)
        SELECT id FROM code_section_full_names WHERE name = ?
    """
    db.execute(sql, (name,))


def is_name_defined_by_code_section(db: sqlite3.Connection, name: str) -> bool:
    # The results of this function can only be trusted _after_ scanner.resolve_all_abbreviations has been called.
    sql = """
        SELECT COUNT(*)
        FROM document_sections
        JOIN document_section_kinds ON document_sections.kind_id = document_section_kinds.id
        WHERE description = 'code'
            AND name = ?
    """
    return db.execute(sql, (name,)).fetchone()[0] != 0
