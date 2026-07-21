from typing import Dict, List

from app.core.entities.document import DocumentChunk
from app.core.interfaces.document_parser import IDocumentParser


class TextDocumentParser(IDocumentParser):

    def supports(self, file_extension: str) -> bool:
        return file_extension in (".txt", ".csv", ".md")

    def parse(self, file_path: str, file_name: str, tenant_metadata: Dict[str, str]) -> List[DocumentChunk]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return [DocumentChunk(
            content=f"ATTENTION LLM: FILE: '{file_name}'\n" + content,
            metadata={"source": file_name, "page": 1, **tenant_metadata},
        )]
