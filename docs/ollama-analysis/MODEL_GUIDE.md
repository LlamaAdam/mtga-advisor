# Local Ollama model guide (August 2026)

Which local models to use for (a) reviewing the `commander-builder` codebase
and (b) powering `commander-builder`'s own local-LLM analyst/proposer path
(`analyst.py` / `proposer.py`, current default `llama3.2:3b`).

Recommendations are drawn from current rankings ([Morph's Ollama
rankings](https://www.morphllm.com/best-ollama-models),
[LocalAIMaster](https://localaimaster.com/blog/best-ollama-models),
[serverman](https://www.serverman.co.uk/ai/ollama/best-ollama-models-for-coding/),
[PromptQuorum](https://www.promptquorum.com/local-llms/top-open-source-models-ollama)),
sized by what your machine can actually hold.

## Code-review role (reads Python, finds bugs)

| Hardware | Model | Why |
|---|---|---|
| 24GB+ VRAM | `qwen3-coder:30b` | 30B MoE (3.3B active) — top local coder, 256K context, ~19GB at Q4 |
| 16-24GB | `devstral:24b` | Best agentic/multi-file review numbers at its size (46.8% SWE-Bench Verified) |
| ~16GB | `gpt-oss:20b` | OpenAI open-weights, o3-mini-level with adjustable reasoning effort, MXFP4 fits 16GB |
| 8-12GB | `qwen2.5-coder:7b` | Still the strongest small code-specialist |
| CPU-only / 8GB | `qwen2.5-coder:3b` | Best quality-per-token below 7B |

## Analyst role (reads sim deltas, argues about Commander decks)

| Hardware | Model | Why |
|---|---|---|
| 16GB+ | `qwen3:14b` | Thinking-mode toggle per request — reasoning when you need it, fast chat when you don't |
| 16GB | `gpt-oss:20b` | Strongest general reasoner that fits 16GB |
| 8-12GB | `deepseek-r1:8b` | Distilled step-by-step reasoner, good verdict quality |
| CPU-only / 8GB | `llama3.1:8b` / `llama3.2:3b` | Solid generalist floor; 3.2:3b is the app's current default |

### What about Meta's Muse Glimmer?

[Muse Glimmer](https://www.bloomberg.com/news/articles/2026-08-10/meta-releases-muse-glimmer-ai-model-people-can-run-on-their-laptop)
(released 2026-08-10) is a 30B Apache-2.0 open-weight agentic model — a
distilled Muse Spark aimed exactly at local tool-calling agents, 131K context,
text+image. It is a real candidate for the analyst role **if** you have
~20GB+ of VRAM/unified memory for a Q4 quant; it will not fit a 15GB
machine. As of mid-August 2026 it ships via Hugging Face
([meta-models/Muse-Glimmer-30B](https://huggingface.co/meta-models/Muse-Glimmer-30B));
check `ollama pull` availability before wiring it in. On paper it beats
Gemma-class 30B peers and its tool-calling focus matches
`proposer.py`'s JSON-manifest workflow well.

## Suggested `commander-builder` config change

`analyst.py:78` and `proposer.py:108` default to `llama3.2:3b`. On any
machine with ≥12GB free, better defaults are:

- **analyst** (`ollama_verdict`): `qwen3:14b` (or `deepseek-r1:8b` at 12GB)
- **proposer** (`ollama_propose`): `qwen3:14b` — card-swap proposals need MTG
  world knowledge; generalists beat code-specialists here
- both paths already use Ollama's `format: "json"` mode, which all models
  above support

## Running the review harness

On a machine with Ollama installed and a model pulled:

```bash
ollama pull qwen2.5-coder:7b
python docs/ollama-analysis/run_local_review.py ~/code/commander-builder \
    --model qwen2.5-coder:7b            # code-review pass
python docs/ollama-analysis/run_local_review.py ~/code/commander-builder \
    --model qwen3:14b --persona analyst --chat   # MTG-domain pass + REPL
```

## Why this couldn't run in the Claude Code cloud session

The remote session's network egress policy allows GitHub (git, raw,
release assets) and package registries (PyPI/npm) only. Verified blocked:
`ollama.com`, `registry.ollama.ai` (`ollama pull` → `Forbidden`),
`huggingface.co`, Docker Hub/ghcr/quay blob hosts, archive.org,
SourceForge, ModelScope — i.e. every LLM-weight distribution channel. The
Ollama **server** itself (v0.32.10, fetched from GitHub releases) runs
fine in the container; there is simply no policy-permitted source of
weights. To enable true in-session runs, add `ollama.com` and
`registry.ollama.ai` to the environment's network allowlist in the
Claude Code environment settings (see
[docs](https://code.claude.com/docs/en/claude-code-on-the-web)).
