import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("users", "0001_initial"),
        ("knowledge", "0011_knowledgeworkflow_default_model_setting_and_more"),
        ("models_provider", "0001_initial"),
        ("application", "0015_application_default_model_setting_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("slug", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=128)),
                ("workspace_id", models.CharField(max_length=64, default="default")),
                ("owner", models.ForeignKey(to="users.user", on_delete=django.db.models.deletion.PROTECT)),
                ("applications", models.ManyToManyField(to="application.application", blank=True)),
                ("models", models.ManyToManyField(to="models_provider.model", blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProjectKnowledge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project", models.ForeignKey(to="litekb_api.project", on_delete=django.db.models.deletion.CASCADE,
                                              related_name="knowledge_grants")),
                ("knowledge", models.OneToOneField(to="knowledge.knowledge", on_delete=django.db.models.deletion.CASCADE,
                                                   related_name="project_grant")),
            ],
        ),
        migrations.CreateModel(
            name="ServiceClient",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=128)),
                ("key_hash", models.CharField(max_length=64, unique=True, editable=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(to="litekb_api.project", on_delete=django.db.models.deletion.CASCADE,
                                              related_name="clients")),
            ],
        ),
    ]
