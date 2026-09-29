@AGENTS.md

## Working with this repo in Claude Code

- Commits and PRs belong to the user: author Triet Le, plain one-line messages, no `Co-Authored-By` trailer and no "Generated with Claude Code" line.
- Changes reach `main` through a branch the user merges as a GitHub PR: commit on the branch, push the branch, hand over the PR link. UI work lives on `frontend`; corpus rebuilds on `corpus-build` (README → Corpus).
- `python -m evals.cases` calls the live DeepSeek API and costs money; run it for agent or prompt changes (AGENTS.md) or when asked. `pytest` and `evals.retrieval` are offline and free.
- The UI is `public/index.html` (static, no build step). It renders the `report` object from `POST /api/assess`, built by `src/report.py`; the contract is the shape of `build_report`'s return value.
- Windows checkout uses `core.autocrlf=true`, so files written with LF show as modified. Judge real changes with `git diff`, which normalises line endings.
