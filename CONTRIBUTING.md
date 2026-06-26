# Contributing to Lucent

This project uses a lightweight, changelog-driven workflow.

## Branching & merges
- `main` is always releasable.
- Do work on a short-lived branch: `feature/...`, `fix/...`, or `chore/...`.
- Open a pull request into `main`. Merge with a **merge commit** (`--no-ff`) so
  each feature stays a discoverable unit in history.

## Commit messages
Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add bulk tagging to the ledger
fix: correct ICICI international wrap parsing
chore: bump dependencies
docs: expand README setup
```

## Changelog
Every user-facing change gets an entry under `## [Unreleased]` in
[CHANGELOG.md](CHANGELOG.md), grouped as Added / Changed / Fixed / Removed.
On release, rename `Unreleased` to the new version + date and tag it:

```bash
git tag -a v0.5.0 -m "v0.5.0"
git push --tags
```

## Versioning
[Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`.
- **MINOR** for new features, **PATCH** for fixes, **MAJOR** for breaking changes.

## Local development
```bash
python3 -m pip install -r requirements.txt
python3 app.py            # auto-picks a free port (skips AirPlay :5000) & prints the URL
```
Double-clicking `run.command` (macOS) does the same and opens your browser.
Pin a port with `PORT=9000 python3 app.py`. Use `LUCENT_DB=/tmp/x.db` to run
against a throwaway database without touching your real ledger.

## Never commit
Local financial data. `data/`, `*.db`, `*.pdf`, and `*.xlsx` are gitignored —
keep it that way.
