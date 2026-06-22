# Versioning Guide

This Python platform is versioned with Git.

## Before Each Change

Check the current state:

```powershell
git status
```

## Save A Version

After a change is tested:

```powershell
git add .
git commit -m "Describe the change"
```

For bigger milestones, create a tag:

```powershell
git tag v0.2.0
```

## See Version History

```powershell
git log --oneline --decorate
```

## Roll Back To A Previous Version

To inspect an old version:

```powershell
git checkout v0.1.0
```

To return to the latest working branch:

```powershell
git checkout main
```

To permanently undo back to a tagged version, ask Codex first so we can protect any newer work before resetting.

## Files Not Versioned

These are intentionally ignored:

- `.venv/`
- `.env`
- local SQLite database files in `data/`
- Python cache files
- local logs and test caches

This keeps secrets and local runtime data out of version history.

