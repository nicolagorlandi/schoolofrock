from django.db import migrations


def add_presenze_mensili_menu_item(apps, schema_editor):
    MenuItem = apps.get_model('documenti', 'MenuItem')
    menu_corsi, _ = MenuItem.objects.get_or_create(
        label='Corsi',
        url_name='corsi:elenco',
        parent=None,
        defaults={
            'icon': 'fa-solid fa-graduation-cap',
            'ordine': 3,
            'visible': True,
        },
    )
    MenuItem.objects.get_or_create(
        label='Presenze Mensili',
        url_name='corsi:presenze-mensili',
        parent=menu_corsi,
        defaults={
            'icon': 'fa-solid fa-chart-column',
            'ordine': 4,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0006_lezioni_ora_inizio'),
    ]

    operations = [
        migrations.RunPython(
            add_presenze_mensili_menu_item,
            migrations.RunPython.noop,
        ),
    ]
