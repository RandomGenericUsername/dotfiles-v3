class ParsingError(Exception):
    def __init__(self, raw: str, message: str = "Failed to parse output"):
        self.raw = raw
        super().__init__(message)
