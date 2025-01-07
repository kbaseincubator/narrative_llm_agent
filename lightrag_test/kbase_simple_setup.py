"""
Just do a "simple" version of db insertion using the JSON files from the catalog.
This uses GPT-4o as the embedding model
"""

from lightrag_test.util import get_catalog_files

import os
from lightrag import LightRAG
# from lightrag.llm import gpt_4o_mini_complete
from lightrag.llm import ollama_model_complete, ollama_embedding
from lightrag.utils import EmbeddingFunc
from pathlib import Path

#########
# Uncomment the below two lines if running in a jupyter notebook to handle the async nature of rag.insert()
# import nest_asyncio
# nest_asyncio.apply()
#########

OLLAMA_MODEL_NAME = "llama31-32k-ctx"
WORKING_DIR = f"./kbase_simple_{OLLAMA_MODEL_NAME}_processed"

if not os.path.exists(WORKING_DIR):
    os.mkdir(WORKING_DIR)

rag = LightRAG(
    working_dir=WORKING_DIR,
    llm_model_func = ollama_model_complete,
    llm_model_name = OLLAMA_MODEL_NAME,
    llm_model_kwargs={"host": "http://localhost:11434", "options": {"num_ctx": 32768}},
    embedding_func=EmbeddingFunc(
        embedding_dim=768,
        max_token_size=8192,
        func=lambda texts: ollama_embedding(
            texts,
            embed_model="nomic-embed-text",
            host="http://localhost:11434"
        )
    )
)

files = get_catalog_files(Path(__file__).parent.parent / "catalog_dump_processed", "txt")
counter = 1
total = len(files)
print(f"processing {total} files")
for file_path in files:
    print(f"{counter}/{total}: {file_path}")
    with open(file_path, "r", encoding="utf-8") as infile:
        rag.insert(infile.read())
    counter += 1

