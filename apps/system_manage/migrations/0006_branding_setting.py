from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('system_manage', '0005_resourcemapping')]
    operations = [
        migrations.AlterField(
            model_name='systemsetting',
            name='type',
            field=models.IntegerField(choices=[(0, '邮箱'), (1, '私钥秘钥'), (2, '日志清理时间'), (3, '品牌')],
                                      default=0, primary_key=True, serialize=False, verbose_name='设置类型'),
        ),
    ]
