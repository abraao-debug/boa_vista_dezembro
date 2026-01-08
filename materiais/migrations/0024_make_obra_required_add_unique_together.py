# Generated manually on 2026-01-07
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('materiais', '0023_remove_destinoentrega_unique_add_obra'),
    ]

    operations = [
        # Torna o campo obra obrigatório
        migrations.AlterField(
            model_name='destinoentrega',
            name='obra',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='destinos',
                to='materiais.obra',
                verbose_name='Obra'
            ),
        ),
        # Adiciona unique_together
        migrations.AlterUniqueTogether(
            name='destinoentrega',
            unique_together={('obra', 'nome')},
        ),
    ]
