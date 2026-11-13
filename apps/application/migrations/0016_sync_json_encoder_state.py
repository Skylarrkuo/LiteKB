from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models

from common.encoder.encoder import SystemEncoder


class Migration(migrations.Migration):
    dependencies = [("application", "0015_application_default_model_setting_and_more")]

    # These model attributes affect Python serialization and labels only. No existing row needs rewriting.
    operations = [
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.AlterField(
                model_name="application", name="work_flow",
                field=models.JSONField(default=dict, encoder=SystemEncoder, verbose_name="工作流数据"),
            ),
            migrations.AlterField(
                model_name="applicationversion", name="work_flow",
                field=models.JSONField(default=dict, encoder=SystemEncoder, verbose_name="工作流数据"),
            ),
            migrations.AlterField(
                model_name="chatrecord", name="answer_text_list",
                field=ArrayField(models.JSONField(encoder=SystemEncoder), default=list, verbose_name="改进标注列表"),
            ),
            migrations.AlterField(
                model_name="applicationchatuserstats", name="access_num",
                field=models.IntegerField(default=0, verbose_name="访问总次数"),
            ),
        ]),
    ]
