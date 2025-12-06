import os
from django.db import migrations


def read_sql_file(filename):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base_dir, 'sql', filename)

    with open(sql_path, 'r', encoding='utf-8') as f:
        return f.read()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('audit', '0001_initial'),
        ('core', '0001_initial'),
        ('goals', '0001_initial'),
        ('habits', '0001_initial'),
        ('categories', '0001_initial'),
        ('challenges', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=read_sql_file('../sql/audit_triggers.sql'),
            reverse_sql=read_sql_file('../sql/drop_audit_triggers.sql'),
        ),
    ]