"""Splits any parsed document longer than a safe char budget into
retrieval-sized chunks, preserving a trailing extracted-tables block intact
on every sub-chunk so table context never gets orphaned by a text split."""
from typing import List

from langchain_core.documents import Document as LcDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.entities.document import DocumentChunk
from app.core.interfaces.document_parser import IDocumentChunker

SAFE_PAGE_CHAR_LIMIT = 3000
TABLE_MARKER = "### Extracted Document Tables:"


class RecursiveDocumentChunker(IDocumentChunker):

    def __init__(self, chunk_size: int = 2500, chunk_overlap: int = 300):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len
        )

    def chunk(self, documents: List[DocumentChunk]) -> List[DocumentChunk]:
        final_chunks: List[DocumentChunk] = []

        for doc in documents:
            if len(doc.content) <= SAFE_PAGE_CHAR_LIMIT:
                final_chunks.append(doc)
                continue

            if TABLE_MARKER in doc.content:
                narrative, table_block = doc.content.split(TABLE_MARKER, 1)
                table_block = TABLE_MARKER + table_block
            else:
                narrative, table_block = doc.content, ""

            sub_docs = self._splitter.split_documents(
                [LcDocument(page_content=narrative, metadata=doc.metadata)]
            )
            for sub in sub_docs:
                content = sub.page_content
                if table_block:
                    content += "\n\n" + table_block
                final_chunks.append(DocumentChunk(content=content, metadata=dict(sub.metadata)))

        return final_chunks
