from django.db import migrations
from django.db.models import Q


def retire_schedules(apps, schema_editor):
    jobs = apps.get_model("django_apscheduler", "DjangoJob")
    jobs.objects.using(schema_editor.connection.alias).filter(
        Q(id__startswith="trigger:") | Q(id__startswith="long_term:application:")
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("trigger", "0002_remove_taskrecord_trigger_task_and_more"),
        ("django_apscheduler", "0009_djangojobexecution_unique_job_executions"),
    ]
    operations = [migrations.RunPython(retire_schedules, migrations.RunPython.noop)]
