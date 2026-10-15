# DSO 429 HW3 — Hourly Quiz

A GitHub Actions workflow (`.github/workflows/quiz.yml`) runs every 10 minutes. It fetches
`questions.csv` from the course quiz repo and writes `answers/round-NNNN.json` for every round
that has not been answered yet, then pushes the files to `main`.

- `solver.py` parses each question template and computes the answer exactly.
- `run.py` handles fetching, writing answer files, and an LLM fallback (OpenRouter) for any
  question the solver doesn't recognize.
- `test_practice.py` checks the solver against the practice keys (1200/1200 correct).
