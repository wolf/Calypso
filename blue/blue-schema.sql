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
   data TEXT
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
   indent TEXT
);


DROP TABLE IF EXISTS code_section_name;
CREATE TABLE code_section_name (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);


DROP TABLE IF EXISTS non_root_code_section_name;
CREATE TABLE non_root_code_section_name (
    name_id INTEGER NOT NULL UNIQUE
);


DROP TABLE IF EXISTS resolved_code;
CREATE TABLE resolved_code (
    name_id INTEGER NOT NULL UNIQUE,
    code TEXT NOT NULL
);
