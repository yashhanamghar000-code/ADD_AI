from typing import Dict, List

import pytesseract
from PIL import Image

from app.core.entities.document import DocumentChunk
from app.core.interfaces.document_parser import IDocumentParser


class ImageOcrDocumentParser(IDocumentParser):

    def supports(self, file_extension: str) -> bool:
        return file_extension in (".png", ".jpg", ".jpeg", ".tiff")

    def parse(self, file_path: str, file_name: str, tenant_metadata: Dict[str, str]) -> List[DocumentChunk]:
        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            img.close()
        except Exception as e:
            print(f"OCR execution failed on image file: {e}")
            text = ""

        return [DocumentChunk(
            content=f"ATTENTION LLM: IMAGE FILE: '{file_name}'\n[System Note: Text extracted via OCR]\n" + text,
            metadata={"source": file_name, "page": 1, "is_image": True, **tenant_metadata},
        )]
