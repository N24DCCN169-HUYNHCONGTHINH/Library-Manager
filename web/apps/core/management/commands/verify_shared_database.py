from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Verify that the configured shared PostgreSQL database is reachable and migrated."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")

    def handle(self, *args, **options):
        alias = options["database"]
        connection = connections[alias]
        config = connection.settings_dict
        if connection.vendor != "postgresql":
            raise CommandError(f"Database '{alias}' is {connection.vendor}; shared database verification requires PostgreSQL.")

        host = config.get("HOST") or "localhost"
        sslmode = config.get("OPTIONS", {}).get("sslmode", "prefer")
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if host.lower() not in local_hosts and sslmode not in {"verify-full", "verify-ca"}:
            raise CommandError("Remote PostgreSQL must use sslmode=verify-full or verify-ca.")

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user, current_setting('server_version')"
                )
                database, user, server_version = cursor.fetchone()
            # Check TLS on Django's client connection. Neon poolers may terminate
            # client TLS before forwarding a backend session, so pg_stat_ssl can
            # report false for the Postgres-side connection even when TLS is active.
            psycopg_connection = connection.connection
            ssl_active = getattr(getattr(psycopg_connection, "pgconn", None), "ssl_in_use", None)
            if ssl_active is None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT COALESCE((SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()), FALSE)"
                    )
                    ssl_active = cursor.fetchone()[0]
        except Exception as exc:
            raise CommandError(
                f"Could not connect to PostgreSQL ({type(exc).__name__}). Check host, TLS and credentials locally."
            ) from exc

        if host.lower() not in local_hosts and not ssl_active:
            raise CommandError("Connection reached PostgreSQL, but the server reports that TLS is not active.")

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.stdout.write(self.style.SUCCESS("Connected to PostgreSQL."))
        self.stdout.write(f"Database: {database}")
        self.stdout.write(f"User: {user}")
        self.stdout.write(f"Host: {host}:{config.get('PORT') or 5432}")
        self.stdout.write(f"Server version: {server_version}")
        self.stdout.write(f"TLS active: {'yes' if ssl_active else 'local connection'} (sslmode={sslmode})")
        if pending:
            self.stderr.write(self.style.ERROR(f"Pending migrations: {len(pending)}"))
            for migration, backwards in pending:
                self.stderr.write(f"  {migration.app_label}.{migration.name}")
            raise CommandError("Run approved migrations as the designated migration operator, then verify again.")
        self.stdout.write(self.style.SUCCESS("No pending migrations."))
