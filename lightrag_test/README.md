This is a test directory for tinkering with [LightRAG](https://github.com/HKUDS/LightRAG) with the KBase app catalog.

First, you might want to download the catalog. See `../scripts/download_kbase_catalog.py` for that task.

Next, in here there are various scripts that initialize LightRAG and
use various LLMs / APIs to do the embedding and vector database creation.

You need a LLM with at least a 32k context window to do the embedding with LightRAG. You can just use one of the gpt-4s (probably 3 also). Or, to do this locally with Ollama, you can either use a larger model (i.e. llama3.3) or craft your own with these commands:

1. First, pull the model you want to use.
```
> ollama pull llama3.1
```
2. Then dump the model file to text
```
> ollama show --modelfile llama3.1 > llama31_32k_ctx_modelfile
```
3. Edit your dumped modelfile by adding this line:
```
PARAMETER num_ctx 32768
```
4. Finally, create the new model from the file
```
ollama create -f llama31_32k_ctx_modelfile llama31-32k-ctx
```

You can now reference `llama31-32k-ctx` as your model.

This info is also available in the LightRAG repo readme. I switched to llama here, as I'm not sure if LBL/DoE cares about using Qwen models.
