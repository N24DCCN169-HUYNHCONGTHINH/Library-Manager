# Contributing

## Team workflow

- Use `main` only for reviewed, working changes. Create a short-lived branch per task: `feat/catalog-list`, `feat/loan-return`, `fix/login-role`.
- Open a pull request; have at least one teammate review it before merging.
- Keep pull requests focused and explain how to verify the change.
- Never commit `.env`, passwords, real reader data, database files, backups, or payment credentials.
- Use synthetic data in development.

## Definition of done

A task is done when its acceptance criteria are met, the change is integrated with the current project, and the contributor documents any setup or operational change. For data-changing flows, check invalid input, duplicate submission, and permission boundaries.

## First tasks

See `docs/plan-13-ngay.md`. Agree on model and route names before multiple contributors edit the same files. Start with one shared development database schema and commit migrations with model changes.
