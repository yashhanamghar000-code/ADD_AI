"""
Open/Closed Principle in action: adding support for a new file type means
writing one new IDocumentParser and registering it here — nothing else in
the ingestion pipeline changes.
"""
import os
from typing import List

from app.core.interfaces.document_parser import IDocumentParser


class UnsupportedFileTypeError(Exception):
    pass


class ParserFactory:

    def __init__(self, parsers: List[IDocumentParser]):
        self._parsers = parsers

    def get_parser(self, file_name: str) -> IDocumentParser:
        extension = os.path.splitext(file_name)[1].lower()
        for parser in self._parsers:
            if parser.supports(extension):
                return parser
        raise UnsupportedFileTypeError(f"Unsupported file format: {extension}")
