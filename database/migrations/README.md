# Database migrations

The original tables are created by `schema.sql`. Alembic owns every schema
change after that baseline.

```bash
alembic upgrade head
```

Never edit a migration that has been applied outside local development. Add a
new revision instead.
