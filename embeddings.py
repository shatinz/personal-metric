from sentence_transformers import SentenceTransformer
import numpy as np

class Embedder:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        print(f"Loading embedding model: {model_name}...")
        try:
            self.model = SentenceTransformer(model_name)
            print("Model loaded successfully.")
        except Exception as e:
            print(f"Failed to load model: {e}")
            self.model = None

    def embed_text(self, text):
        if not self.model:
            return None
        if not text or not text.strip():
            return None
            
        embedding = self.model.encode(text)
        return embedding

    def serialize_embedding(self, embedding):
        """Convert numpy array to bytes for storage."""
        if embedding is None:
            return None
        return embedding.tobytes()

    def deserialize_embedding(self, blob):
        """Convert bytes back to numpy array."""
        if blob is None:
            return None
        return np.frombuffer(blob, dtype=np.float32)

if __name__ == "__main__":
    e = Embedder()
    if e.model:
        vec = e.embed_text("Hello OneNote!")
        print(f"Embedding shape: {vec.shape}")
