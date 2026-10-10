from django.db import migrations, models


def inizializza_data_ricorrenza(apps, schema_editor):
    Lezioni = apps.get_model('Corsi', 'Lezioni')
    Lezioni.objects.filter(data_ricorrenza__isnull=True).update(
        data_ricorrenza=models.F('data')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0005_menu_item_calendario_lezioni'),
    ]

    operations = [
        migrations.AddField(
            model_name='lezioni',
            name='data_ricorrenza',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(
            inizializza_data_ricorrenza,
            migrations.RunPython.noop,
        ),
        migrations.AddField(
            model_name='lezioni',
            name='ora_inizio',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
