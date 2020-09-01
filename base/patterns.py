import re


DOCUMENTATION_BLOCK_START_PATTERN = re.compile(r"^@$")

CODE_BLOCK_START_PATTERN = re.compile(r"^<<(.*)>>=$")

CODE_BLOCK_REFERENCE_PATTERN = re.compile(
    r"""
    (?P<indent>[ \t]*)
    (?P<complete_reference>                    # to throw away the delimiters we need to know where they are
        <<(?P<just_the_referenced_name>.*?)>>  # there may be more than one reference on the line, so be non-greedy
    )
    """,
    re.VERBOSE,
)

INCLUDE_STATEMENT_PATTERN = re.compile(r"^@include\((.*)\)$")

BAD_SECTION_NAME_PATTERN = re.compile(r"<<|>>")
