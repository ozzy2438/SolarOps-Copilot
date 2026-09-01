# Migrations

Plain SQL, applied in filename order. **Not Alembic** — ADR-0004 records why: this
schema is small, changes rarely, and the Docker Compose stack applies these files by
mounting the directory into the PostgreSQL image's `docker-entrypoint-initdb.d`. A
migration framework would add a dependency and a code path for a problem this project
does not have.

## Rules

- Files are `NNNN_name.sql`, numbered sequentially. Never renumber an existing file.
- Every statement is idempotent (`IF NOT EXISTS`), so re-running the directory is safe.
- **Never edit a committed migration.** Add a new one. A later phase that edits `0001`
  leaves every existing database in a state no migration describes.
- A change to a contract in `voltdesk/contracts/` that adds a persisted field needs a
  migration in the same change. A contract field with no column is silent data loss.

## Applying them

Locally, `docker compose up` applies them on first start of an empty volume. Against
an existing database:

```bash
for f in migrations/*.sql; do psql "$VOLTDESK_DATABASE_URL" -f "$f"; done
```

`docker compose down -v` drops the volume, so the next `up` re-applies everything from
scratch. That is the intended way to pick up a new migration locally.
