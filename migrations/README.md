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
a running stack, without needing a published host port:

```bash
for f in migrations/*.sql; do
  docker compose exec -T postgres psql -U voltdesk -d voltdesk -v ON_ERROR_STOP=1 -f - < "$f"
done
```

Against a database reachable from the host, once you have its real URL (see
`docker-compose.hostports.yml`):

```bash
for f in migrations/*.sql; do psql "$VOLTDESK_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"; done
```

`ON_ERROR_STOP=1` matters: without it psql reports success after a failed statement.

To pick up a new migration locally you can either apply it with the loop above, or
start from an empty volume with `make destroy && make up`. **`make destroy` deletes
VoltDesk's postgres and espocrm volumes and everything in them** — it prompts for
confirmation for that reason. `make down` only stops the stack and keeps the data.
