from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0016_alunno_ricevuta_iscrizione_corso_prezzo_iscrizione'),
    ]

    operations = [
        migrations.AddField(
            model_name='alunno',
            name='prezzo',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Prezzo',
            ),
        ),
    ]
