PRAGMA foreign_keys = ON;


DROP TABLE IF EXISTS document_section_kind;
CREATE TABLE document_section_kind (
    id INTEGER PRIMARY KEY NOT NULL,
    description TEXT NOT NULL
);
INSERT INTO document_section_kind (description) VALUES
    ('documentation'),
    ('code')
;


DROP TABLE IF EXISTS document_section;
CREATE TABLE document_section (
    id INTEGER PRIMARY KEY NOT NULL,
    kind_id INTEGER NOT NULL,
    is_included INTEGER, -- 0 or 1 (because there is no BOOLEAN type)
    code_section_presentation_number INTEGER, -- will be NULL for kinds other than 'code'
    sequence REAL,
    name TEXT COLLATE NOCASE, -- will be NULL for kinds other than code
    data TEXT,

    FOREIGN KEY (kind_id) REFERENCES document_section_kind(id)
);


DROP TABLE IF EXISTS fragment_kind;
CREATE TABLE fragment_kind (
    id INTEGER PRIMARY KEY NOT NULL,
    description TEXT NOT NULL
);
INSERT INTO fragment_kind (description) VALUES
    ('plain text'),
    ('reference')
;


DROP TABLE IF EXISTS fragment;
CREATE TABLE fragment (
    id INTEGER PRIMARY KEY NOT NULL,
    kind_id INTEGER NOT NULL,
    parent_id INTEGER NOT NULL,
    parent_name_id INTEGER,
    sequence REAL,
    data TEXT,
    indent TEXT,

    FOREIGN KEY (kind_id) REFERENCES fragment_kind(id),
    FOREIGN KEY (parent_id) REFERENCES document_section(id),
    FOREIGN KEY (parent_name_id) REFERENCES code_section_name(id)
);


DROP TABLE IF EXISTS code_section_name;
CREATE TABLE code_section_name (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);


DROP TABLE IF EXISTS non_root_code_section_name;
CREATE TABLE non_root_code_section_name (
    name_id INTEGER NOT NULL UNIQUE,

    FOREIGN KEY (name_id) REFERENCES code_section_name(id)
);


DROP TABLE IF EXISTS resolved_code;
CREATE TABLE resolved_code (
    name_id INTEGER NOT NULL UNIQUE,
    code TEXT NOT NULL
);
