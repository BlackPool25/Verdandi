# Team workflow — Verdandi

`main` is always green and always deployable via `docker compose up --build`.
All work happens on short-lived branches, merged by squash after CI + 1 review.

## Setup (new machine)
```bash
git clone https://github.com/BlackPool25/Verdandi.git && cd Verdandi
git config pull.rebase true && git config rebase.autostash true
pip install -r requirements.txt -r requirements-ci.txt
./run.sh --no-browser   # smoke test: sim bridge + frontend
```

## Daily loop
```bash
git checkout main && git pull --rebase          # start fresh
git checkout -b fix/<slug>                     # or feat/<slug>
# ... edit, one sentence per line in docs, small commits ...
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/
python -m pytest tests/ -m "k1 or battery" -n auto -q
git push -u origin fix/<slug>                  # open PR, fill the template
```
Merge only after CI is green + 1 review. Then locally: `git checkout main && git pull --rebase`.

## Second machine / teammate's change
```bash
git fetch origin && git checkout main && git pull --rebase
git log --oneline -5   # see what landed
```

## Rules
- Never push to `main`. Never `--force` a shared branch (`--force-with-lease` on your own branch only).
- Gate bars (`check_gates.py` defaults, README table) change only with L1 reclassification + reviewer sign-off.
- One branch = one task. Stale branch > 1 week: rebase or close it.
