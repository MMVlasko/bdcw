import os
from django.db import migrations


def read_sql_file(filename):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base_dir, 'sql', filename)

    with open(sql_path, 'r', encoding='utf-8') as f:
        return f.read()


class Migration(migrations.Migration):
    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            sql=read_sql_file('../sql/functions_and_views_create.sql'),
            reverse_sql=read_sql_file('../sql/functions_and_views_drop.sql')
        )
    ]