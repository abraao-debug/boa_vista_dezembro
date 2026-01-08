# Generated manually on 2026-01-07
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materiais', '0021_alter_cotacao_unique_together_cotacao_conformidade_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='destinoentrega',
            name='endereco',
            field=models.CharField(blank=True, max_length=300, verbose_name='Endereço Completo'),
        ),
    ]
