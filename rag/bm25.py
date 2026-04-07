import math
from typing import List


class SimpleBM25:
    """轻量 BM25，无第三方依赖，适合课程项目。"""

    def __init__(self, corpus_tokenized: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus_tokenized)
        if self.corpus_size == 0:
            self.avgdl = 0.0
            self.doc_freqs = []
            self.doc_len = []
            self.idf = {}
            return

        self.doc_len = [len(doc) for doc in corpus_tokenized]
        self.avgdl = sum(self.doc_len) / self.corpus_size
        self.doc_freqs = []
        df = {}
        for doc in corpus_tokenized:
            freqs = {}
            for w in doc:
                freqs[w] = freqs.get(w, 0) + 1
            self.doc_freqs.append(freqs)
            for w in freqs:
                df[w] = df.get(w, 0) + 1

        self.idf = {}
        for word, freq in df.items():
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        if self.corpus_size == 0 or self.avgdl == 0:
            return []

        scores = [0.0] * self.corpus_size
        for i in range(self.corpus_size):
            doc = self.doc_freqs[i]
            dl = self.doc_len[i]
            for q in query_tokens:
                if q not in doc:
                    continue
                freq = doc[q]
                idf = self.idf.get(q, 0.0)
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += idf * (freq * (self.k1 + 1)) / denom
        return scores
