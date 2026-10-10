from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0007_menu_item_presenze_mensili'),
    ]

    operations = [
        migrations.AddField(
            model_name='corso',
            name='descrizione',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
