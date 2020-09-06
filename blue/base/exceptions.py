class CodeReaderError(RuntimeError):
    def __init__(self, message):
        self.message = message


class BadSectionNameError(CodeReaderError):
    pass


class CodeSectionRecursionError(CodeReaderError):
    pass


class NoSuchCodeSectionError(CodeReaderError):
    pass


class NoRootCodeSectionsFoundError(CodeReaderError):
    # deprecated
    pass


class FileIncludeRecursionError(CodeReaderError):
    pass


class NonUniqueAbbreviationError(CodeReaderError):
    pass


class ParsingTasksCalledOutOfSequence(CodeReaderError):
    pass
