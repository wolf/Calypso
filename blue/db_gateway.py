from contextlib import contextmanager
from typing import Generator, Optional

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


def insert_document_section(
    db: sqlite3.Connection,
    kind: str,
    data: str,
    is_included: bool,
    name: Optional[str] = None,
    sequence: Optional[float] = None,
):
    sql = """
        INSERT INTO document_section (kind_id, is_included, name, data, sequence) VALUES (
            (SELECT id FROM document_section_kind WHERE description = ?),
            ?, ?, ?, ?
        )
    """
    db.execute(sql, (kind, int(is_included), name, data, sequence))


def document_sections_in_order(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT
            document_section.id,
            description AS kind,
            code_section_presentation_number,
            name
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        ORDER BY sequence
    """
    for row in db.execute(sql):
        yield row


def raw_document_sections_in_order(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT id, data FROM document_section ORDER BY sequence
    """
    for row in db.execute(sql):
        yield row


def code_section_ids_in_order(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT code_section.id
        FROM document_section code_section
        JOIN document_section_kind ON document_section_kind.id = code_section.kind_id
        WHERE document_section_kind.description = 'code'
            AND is_included = 0
        ORDER BY code_section.sequence
    """
    for row in db.execute(sql):
        yield row["id"]


def resolved_code(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT name, code
        FROM resolved_code
        JOIN code_section_name ON id = name_id
    """
    for row in db.execute(sql):
        yield row


def insert_resolved_code(db: sqlite3.Connection, code_section_name_id: int, code: str):
    sql = """
        INSERT OR IGNORE INTO resolved_code (name_id, code) VALUES (?, ?)
    """
    db.execute(sql, (code_section_name_id, code))


def assign_code_section_presentation_number(db: sqlite3.Connection, code_section_id: int, presentation_number: int):
    sql = """
        UPDATE document_section SET code_section_presentation_number = ? WHERE id = ?
    """
    db.execute(sql, (presentation_number, code_section_id))


def assign_code_section_name(db: sqlite3.Connection, code_section_id: int, name: str):
    sql = """
        UPDATE document_section SET name = ? WHERE id = ?
    """
    db.execute(sql, (name, code_section_id))


def assign_reference_fragment_name(db: sqlite3.Connection, fragment_id: int, name: str):
    sql = """
        UPDATE fragment SET data = ? WHERE id = ?
    """
    db.execute(sql, (name, fragment_id))


def insert_fragment(
    db: sqlite3.Connection,
    kind: str,
    parent_id: int,
    data: str,
    indent: str = "",
    sequence: Optional[float] = None,
):
    sql = """
        INSERT INTO fragment (kind_id, parent_id, data, indent, sequence) VALUES (
            (SELECT id FROM fragment_kind WHERE description = ?),
            ?, ?, ?, ?
        )
    """
    db.execute(sql, (kind, parent_id, data, indent, sequence))


def collect_all_unabbreviated_names(db: sqlite3.Connection):
    """
    Search among code-sections for those with unabbreviated names; then search among reference fragments for those whose
    references are unabbreviated.  Save the found names in the code_sections_full_names table.

    I would try to enforce order here so that the first found unabbreviated name then becomes the canonical version with
    respect to capitalization; but that turns out to be hard to do in SQL.
    """

    sql = """
        INSERT OR IGNORE INTO code_section_name (name)
        SELECT name
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        WHERE description = 'code'
            AND name NOT LIKE '%...'
        UNION
        SELECT data AS name
        FROM fragment
        JOIN fragment_kind ON fragment_kind.id = fragment.kind_id
        WHERE description = 'reference'
            AND data NOT LIKE '%...'
    """
    db.execute(sql)


def abbreviated_code_section_names(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT document_section.id, name
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        WHERE description = 'code'
            AND name LIKE '%...'
    """
    for row in db.execute(sql):
        yield row


def abbreviated_reference_fragment_names(db: sqlite3.Connection) -> Generator:
    sql = """
        SELECT fragment.id, data AS name
        FROM fragment
        JOIN fragment_kind ON fragment_kind.id = fragment.kind_id
        WHERE description = 'reference'
            AND data LIKE '%...'
    """
    for row in db.execute(sql):
        yield row


def unabbreviated_names(db: sqlite3.Connection, roots_only: bool = False) -> Generator:
    all_names_sql = """
        SELECT id, name FROM code_section_name
    """
    root_names_sql = """
        SELECT id, name FROM code_section_name
        EXCEPT
        SELECT id, name FROM non_root_code_section_name
        JOIN code_section_name ON code_section_name.id = name_id
    """
    for row in db.execute(root_names_sql if roots_only else all_names_sql):
        yield row


def resolve_abbreviation(db: sqlite3.Connection, abbreviation: str) -> Generator:
    sql = """
        SELECT name FROM code_section_name WHERE name LIKE ?||'%'
    """
    for row in db.execute(sql, (abbreviation,)):
        yield row["name"]


def assign_fragment_parent_name_ids(db: sqlite3.Connection, code_section_name_id: int, code_section_name: str):
    sql = """
        UPDATE fragment SET parent_name_id = ?
        WHERE parent_id IN (
            SELECT id FROM document_section WHERE name = ?
        )
    """
    db.execute(sql, (code_section_name_id, code_section_name))


def fragments_belonging_to_this_name_in_order(db: sqlite3.Connection, code_section_name: str) -> Generator:
    sql = """
        SELECT
            description AS kind,
            parent_id,
            fragment.data,
            indent
        FROM fragment
        JOIN fragment_kind ON fragment_kind.id = fragment.kind_id
        JOIN document_section parent ON parent.id = parent_id
        WHERE parent_name_id = (
            SELECT id FROM code_section_name WHERE name = ?
        )
        ORDER BY parent.sequence, fragment.sequence
    """
    for row in db.execute(sql, (code_section_name,)):
        yield row


def fragments_belonging_to_this_parent_in_order(db: sqlite3.Connection, section_id: int) -> Generator:
    sql = """
        SELECT
            description AS kind,
            fragment.data
        FROM fragment
        JOIN fragment_kind on fragment.kind_id = fragment_kind.id
        WHERE parent_id = ?
    """
    for row in db.execute(sql, (section_id,)):
        yield row


def insert_non_root_name(db: sqlite3.Connection, name: str):
    sql = """
        INSERT OR IGNORE INTO non_root_code_section_name (name_id)
        SELECT id FROM code_section_name WHERE name = ?
    """
    db.execute(sql, (name,))


def collect_non_root_names(db: sqlite3.Connection):
    sql = """
        INSERT OR IGNORE INTO non_root_code_section_name (name_id)
        SELECT code_section_name.id
        FROM fragment
        JOIN code_section_name ON code_section_name.name = fragment.data
        JOIN fragment_kind ON fragment_kind.id = fragment.kind_id
        JOIN document_section parent ON parent.id = parent_id
        JOIN document_section_kind ON document_section_kind.id = parent.kind_id
        WHERE fragment_kind.description = 'reference'
            AND document_section_kind.description = 'code'
    """
    db.execute(sql)


def is_name_defined_by_code_section(db: sqlite3.Connection, name: str) -> bool:
    # The results of this function can only be trusted _after_ scanner.resolve_all_abbreviations has been called.
    sql = """
        SELECT COUNT(*)
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        WHERE description = 'code'
            AND name = ?
    """
    return db.execute(sql, (name,)).fetchone()[0] != 0
