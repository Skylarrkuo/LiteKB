"""Fallback token counts for providers without model-specific usage metadata."""
from functools import lru_cache

import tiktoken


class TokenizerManage:
    @staticmethod
    @lru_cache(maxsize=1)
    def get_tokenizer():
        return _FallbackTokenizer(tiktoken.get_encoding("cl100k_base"))


class _FallbackTokenizer:
    def __init__(self, encoding):
        self.encoding = encoding

    def encode(self, text):
        return self.encoding.encode_ordinary(text)
