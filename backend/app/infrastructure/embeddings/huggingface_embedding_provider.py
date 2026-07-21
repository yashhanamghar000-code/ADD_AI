from typing import List

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.interfaces.embedding_provider import IEmbeddingProvider


class HuggingFaceEmbeddingProvider(IEmbeddingProvider):

    def __init__(self, model_name: str):
        print("[System] Booting Embedding Model... (This might take a moment on first run)")
        self._model = HuggingFaceEmbeddings(model_name=model_name)
        print("[System] Embedding Model ready.")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._model.embed_query(text)