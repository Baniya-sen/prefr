# Prefr — Hermes Preference Engine

## Status: V1 in progress

## Repo
- **GitHub:** https://github.com/Baniya-sen/prefr
- **Local:** ~/hermes-preference-engine/
- **Pi backup:** /mnt/Baniya-Storage/SSD/Personal/projects/hermes-preference-engine/

## Branch Strategy
- `main` — stable, protected, PR-only merges
- `develop` — integration target for feature branches
- `integration` — working branch (only branch Glitch pushes to)
- **Never push to main directly.** All changes go: `integration` → PR → `develop`

## Workflow
1. Create/checkout `integration` branch from `develop`
2. Make changes, commit
3. Push to `origin integration`
4. Create PR: `integration` → `develop`
5. Bhanu reviews and merges on GitHub

## Commands
```bash
# Push to integration
cd ~/hermes-preference-engine
git checkout integration
git add -A && git commit -m "description"
git push origin integration

# Create PR via gh
gh pr create --base develop --head integration --title "title" --body "description"

# List PRs
gh pr list

# Pull latest develop into integration
git fetch origin
git rebase origin/develop
```

## Auth
- gh CLI authenticated as Baniya-sen (PAT via `gh auth login`)
- Git credential helper: gh manages credentials
- Token NOT in remote URL (clean)

## Gotchas
- `engine/` dir is local only (llama.cpp binaries + models, ~4GB, gitignored)
- `evaluator.py` uses absolute import: `from preferences_engine.config import POLICIES`
- llama-server needs `LD_LIBRARY_PATH=./build/bin` to find shared libs
- exFAT on Pi drives — use tar+ssh or `rsync --no-perms --no-owner --no-group --inplace` for Pi sync
- Classifier too conservative — returns `needs_policy: false` for everything. Needs prompt tuning.

## What Was Done (latest session)
- Created repo on GitHub (Baniya-sen/prefr)
- Set up gh CLI + PAT auth on VM
- Established branch workflow: integration → PR → develop
- Added .gitignore for local dev files
- Created PR #5 (gitignore) — merged
- Removed old example testing file
- Synced Python code to Pi backup (tar+ssh, engine/ folders only)

## What Needs To Be Done
1. **Classifier prompt tuning** — too conservative, never fires needs_policy=true
2. **Hermes pre_llm_call plugin** — integrate preference engine into live Hermes
3. **More policies** — create as needed
4. **Pi sync automation** — currently manual tar+ssh
5. **Reflection loop (V2)** — async observation generation, deferred by design

## Last Updated
2026-08-12 00:06 IST
