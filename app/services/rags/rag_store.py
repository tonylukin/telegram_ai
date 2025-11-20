import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_chroma.vectorstores import Chroma

# ---- Chroma client ----
client = chromadb.PersistentClient(path="./chroma_db")

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

# todo we don't use it
def get_vectorstore():
    return Chroma(
        client=client,
        collection_name="docs",
        embedding_function=embedding_model,
    )
