from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("litekb_api", "0002_run_trace")]
    operations = [
        migrations.AddField("run", "lease_owner", models.UUIDField(null=True, editable=False)),
        migrations.AddField("run", "lease_expires_at", models.DateTimeField(null=True, db_index=True)),
        migrations.AddField("run", "active_since", models.DateTimeField(null=True)),
        migrations.AddField("run", "deadline_at", models.DateTimeField(null=True, db_index=True)),
        migrations.AddField("runevent", "effect_key", models.CharField(max_length=64, null=True)),
        migrations.AddConstraint(
            "runevent",
            models.UniqueConstraint(
                fields=["run", "effect_key"], condition=models.Q(effect_key__isnull=False), name="lk_run_effect_once"
            ),
        ),
    ]
