"""End-to-end ASK evaluation: not 'did we retrieve the right note' but 'is the
cited ANSWER good'. The ask is the surface that matters most — non-experts query
memory rather than search, and citations pull experts to ask too.

Fair competition: every retrieval system feeds the SAME generator a cited
answer prompt; an independent local judge (ollama) scores faithfulness,
correctness and honest refusal. Retrieval is the only variable."""
