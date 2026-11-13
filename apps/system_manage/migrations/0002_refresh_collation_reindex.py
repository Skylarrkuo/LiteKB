from django.db import migrations
from psycopg import sql


def re_index(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql" or connection.pg_version < 150000:
        return
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT datname, datcollversion, pg_catalog.pg_database_collation_actual_version(oid)
              FROM pg_catalog.pg_database
             WHERE datname = current_database()
        """)
        name, recorded, current = cursor.fetchone()
        if recorded is None or current is None or recorded == current:
            return
        identifier = sql.Identifier(name)
        cursor.execute(sql.SQL("REINDEX DATABASE {}").format(identifier))
        cursor.execute(sql.SQL("ALTER DATABASE {} REFRESH COLLATION VERSION").format(identifier))


class Migration(migrations.Migration):
    # REINDEX DATABASE must run on the migration connection outside a transaction.
    atomic = False
    dependencies = [("system_manage", "0001_initial")]
    operations = [migrations.RunPython(re_index, atomic=False)]
