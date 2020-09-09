DROP TABLE IF EXISTS document_section_kinds;
CREATE TABLE document_section_kinds (
    id INTEGER PRIMARY KEY NOT NULL,
    description TEXT NOT NULL
);
INSERT INTO document_section_kinds (description) VALUES
    ('documentation'),
    ('code')
;


DROP TABLE IF EXISTS document_sections;
CREATE TABLE document_sections (
   id INTEGER PRIMARY KEY NOT NULL,
   kind_id INTEGER NOT NULL,
   is_included INTEGER, -- 0 or 1 (because there is no BOOLEAN type)
   code_section_sequence_number INTEGER, -- will be NULL for kinds other than 'code'
   name TEXT COLLATE NOCASE, -- will be NULL for kinds other than code
   data TEXT
);


DROP TABLE IF EXISTS fragment_kinds;
CREATE TABLE fragment_kinds (
    id INTEGER PRIMARY KEY NOT NULL,
    description TEXT NOT NULL
);
INSERT INTO fragment_kinds (description) VALUES
    ('plain text'),
    ('reference')
;


DROP TABLE IF EXISTS fragments;
CREATE TABLE fragments (
   id INTEGER PRIMARY KEY NOT NULL,
   kind_id INTEGER NOT NULL,
   parent_document_section_id INTEGER NOT NULL,
   code_section_name_id INTEGER,
   data TEXT,
   indent TEXT
);


DROP TABLE IF EXISTS code_section_full_names;
CREATE TABLE code_section_full_names (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);


DROP TABLE IF EXISTS non_root_code_sections;
CREATE TABLE non_root_code_sections (
    code_section_name_id INTEGER NOT NULL UNIQUE
);


DROP TABLE IF EXISTS resolved_code_sections;
CREATE TABLE resolved_code_sections (
    code_section_name_id INTEGER NOT NULL UNIQUE,
    code TEXT NOT NULL
);
