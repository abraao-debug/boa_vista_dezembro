# Generated manually on 2026-01-07
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('materiais', '0022_destinoentrega_endereco'),
    ]

    operations = [
        # Remove a constraint unique do nome
        migrations.AlterField(
            model_name='destinoentrega',
            name='nome',
            field=models.CharField(max_length=150, verbose_name='Nome do Local'),
        ),
        # Adiciona o campo obra (temporariamente nullable)
        migrations.AddField(
            model_name='destinoentrega',
            name='obra',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='destinos',
                to='materiais.obra',
                verbose_name='Obra'
            ),
        ),
    ]
