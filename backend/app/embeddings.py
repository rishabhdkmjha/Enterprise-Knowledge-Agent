from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from .config import EMBED_MODEL


@lru_cache
def _model() -> TextEmbedding:
    return TextEmbedding(EMBED_MODEL)


def embed(texts: list[str]) -> list[np.ndarray]:
    return [np.asarray(v, dtype=np.float32) for v in _model().embed(texts)]
