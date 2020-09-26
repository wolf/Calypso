class BlueScannerError(RuntimeError):
    def __init__(self, message):
        self.message = message


class BadSectionNameError(BlueScannerError):
    pass


class CodeSectionRecursionError(BlueScannerError):
    pass


class NoSuchCodeSectionError(BlueScannerError):
    pass


class NoRootCodeSectionsFoundError(BlueScannerError):
    pass


class FileIncludeRecursionError(BlueScannerError):
    pass


class NonUniqueAbbreviationError(BlueScannerError):
    pass


class ParsingTasksCalledOutOfSequence(BlueScannerError):
    pass
