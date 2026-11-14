"""Judge registry: display name -> (Hugging Face repo, GGUF file)."""

JUDGES = {
    "qwen2.5-coder-1.5b": ("Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF", "qwen2.5-coder-1.5b-instruct-q8_0.gguf"),
    "qwen2.5-coder-3b": ("Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", "qwen2.5-coder-3b-instruct-q4_0.gguf"),
    "qwen3-1.7b": ("Qwen/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q8_0.gguf"),
    "qwen3-4b": ("unsloth/Qwen3-4B-GGUF", "Qwen3-4B-Q4_0.gguf"),
    "llama-3.2-3b": ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama-3.2-3B-Instruct-Q4_0.gguf"),
    "gemma-3-4b": ("unsloth/gemma-3-4b-it-GGUF", "gemma-3-4b-it-Q4_0.gguf"),
}


def url(name: str) -> str:
    repo, fn = JUDGES[name]
    return f"https://huggingface.co/{repo}/resolve/main/{fn}"


if __name__ == "__main__":
    import sys
    name = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "file":
        print(JUDGES[name][1])
    else:
        print(url(name))
