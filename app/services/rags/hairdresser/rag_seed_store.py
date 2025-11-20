# rag_store_chroma.py
from chromadb import PersistentClient
from langchain_openai import OpenAIEmbeddings

from app.config import OPENAI_API_KEY


class RAGSeedStore:
    def __init__(self, path: str = "./chroma_db"):
        self.client = PersistentClient(path=path)

        self.embed = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)  # можно заменить на Google или LiteLLM

        self.positive = self.client.get_or_create_collection(
            name="hairdresser_positive_cases",
            metadata={"hnsw:space": "cosine"},
        )

        self.negative = self.client.get_or_create_collection(
            name="hairdresser_negative_cases",
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------
    # Adding examples
    # ------------------------
    def add_positive(self, text: str):
        emb = self.embed.embed_query(text)
        existing = self.positive.query(query_embeddings=[emb], n_results=1)
        if existing and existing.get("documents") and text in existing["documents"][0]:
            print(f"'{text}' already exists in positive collection.")
            return
        new_id = f"pos_{self.positive.count() + 1}"
        self.positive.add(
            embeddings=[emb],
            documents=[text],
            ids=[new_id]
        )
        print(f"Added positive example {new_id}. Total: {self.positive.count()}")

    def add_negative(self, text: str):
        emb = self.embed.embed_query(text)
        existing = self.negative.query(query_embeddings=[emb], n_results=1)
        if existing and existing.get("documents") and text in existing["documents"][0]:
            print(f"'{text}' already exists in negative collection.")
            return
        new_id = f"neg_{self.negative.count() + 1}"
        self.negative.add(
            embeddings=[emb],
            documents=[text],
            ids=[new_id]
        )
        print(f"Added negative example {new_id}. Total: {self.negative.count()}")

    # ------------------------
    # Getting closest examples
    # ------------------------
    def query(self, text: str, k=3):
        emb = self.embed.embed_query(text)

        pos = self.positive.query(query_embeddings=[emb], n_results=k)
        neg = self.negative.query(query_embeddings=[emb], n_results=k)

        return {
            "positive": pos["documents"][0] if pos["documents"] else [],
            "negative": neg["documents"][0] if neg["documents"] else [],
        }
