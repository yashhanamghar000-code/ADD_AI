from typing import List

from sentence_transformers import CrossEncoder

from app.core.entities.document import DocumentChunk
from app.core.interfaces.reranker import IReranker


class CrossEncoderReranker(IReranker):

    def __init__(self, model_name: str):
        print("[Setup] Loading CrossEncoder reranker...")
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: List[DocumentChunk], top_n: int) -> List[DocumentChunk]:
        if not candidates:
            return []
        pairs = [[query, doc.content] for doc in candidates]
        scores = self._model.predict(pairs)
        scored = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        return [doc for _score, doc in scored[:top_n]]
