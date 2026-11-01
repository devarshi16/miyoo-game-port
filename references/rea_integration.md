# Optional reverse-engineering tools

REA can help inventory binaries, inspect managed metadata and investigate original data formats when it is available. It is optional; equivalent local tools are valid. Neither decompilation nor a generated API skeleton establishes behavioral compatibility or produces a working native game by itself.

Keep the sequence evidence-driven: identify the exact build/engine and native dependencies; inspect serialized containers and the API actually exercised; implement a small slice; measure it on the target. Preserve the provenance of extracted data and distribute only authorized runtime/source components. See SKILL.md for validation and packaging requirements.
