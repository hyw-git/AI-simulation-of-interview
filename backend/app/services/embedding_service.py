import hashlib

class FakeEmbeddingService:
    """A deterministic fake embedding generator for local development and testing.
    Produces a fixed-dimension vector (1536) derived from text using hashing.
    Replace this with real model calls in production.
    """
    DIM = 1536

    def embed_text(self, text: str):
        # simple deterministic pseudo-random floats based on sha256
        h = hashlib.sha256(text.encode('utf-8')).digest()
        nums = []
        i = 0
        while len(nums) < self.DIM:
            # expand digest via hashing with counter
            chunk = hashlib.sha256(h + i.to_bytes(4, 'little')).digest()
            for b in chunk:
                if len(nums) >= self.DIM:
                    break
                nums.append((b / 255.0) * 2 - 1)  # scale to [-1,1]
            i += 1
        return nums

