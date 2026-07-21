from typing import Dict, List

import docx

from app.core.entities.document import DocumentChunk
from app.core.interfaces.document_parser import IDocumentParser


class DocxDocumentParser(IDocumentParser):

    def supports(self, file_extension: str) -> bool:
        return file_extension in (".docx", ".doc")

    def parse(self, file_path: str, file_name: str, tenant_metadata: Dict[str, str]) -> List[DocumentChunk]:
        doc = docx.Document(file_path)
        full_text = [para.text for para in doc.paragraphs if para.text.strip()]
        content = "\n".join(full_text)

        return [DocumentChunk(
            content=f"ATTENTION LLM: FILE: '{file_name}'\n" + content,
            metadata={"source": file_name, "page": 1, **tenant_metadata},
        )]
