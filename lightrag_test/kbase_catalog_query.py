from lightrag import LightRAG, QueryParam
from lightrag.llm import gpt_4o_mini_complete
from pathlib import Path

from LightRAG.lightrag.llm import ollama_embedding, ollama_model_complete
from LightRAG.lightrag.utils import EmbeddingFunc

WORKING_DIR = Path(__file__).absolute().parent.parent / "kbase_simple_llama31-32k-ctx_processed"

rag = LightRAG(
    working_dir=WORKING_DIR,
    # llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
    # llm_model_func=gpt_4o_complete  # Optionally, use a stronger model
    llm_model_func=ollama_model_complete,
    llm_model_name="llama31-32k-ctx",
    embedding_func=EmbeddingFunc(
        embedding_dim=768,
        max_token_size=8192,
        func=lambda texts: ollama_embedding(
            texts, embed_model="nomic-embed-text", host="http://localhost:11434"
        ),
    ),
)

print(
    # rag.query(
    #     "What are KBase apps I can use to annotate microbial genomes? Please include the id for each option.",
    #     param=QueryParam(mode="global")
    # )
    rag.query(
        "What are KBase apps I can use to annotate microbial genomes? Please include the id for each option.",
        param=QueryParam(mode="global")
    )
)

# # Perform naive search
# print(rag.query("What are the top themes in this story?", param=QueryParam(mode="naive")))

# # Perform local search
# print(rag.query("What are the top themes in this story?", param=QueryParam(mode="local")))

# # Perform global search
# print(rag.query("What are the top themes in this story?", param=QueryParam(mode="global")))

# # Perform hybrid search
# print(rag.query("What are the top themes in this story?", param=QueryParam(mode="hybrid")))
