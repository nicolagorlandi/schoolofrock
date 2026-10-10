from django.db import migrations


def add_calendario_menu_item(apps, schema_editor):
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
        label='Calendario lezioni',
        url_name='corsi:calendario-lezioni',
        parent=menu_corsi,
        defaults={
            'icon': 'fa-solid fa-calendar-days',
            'ordine': 3,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0004_menu_item_corsi_link'),
    ]

    operations = [
        migrations.RunPython(add_calendario_menu_item, migrations.RunPython.noop),
    ]
