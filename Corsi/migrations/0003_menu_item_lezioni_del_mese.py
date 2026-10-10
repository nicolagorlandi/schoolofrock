from django.db import migrations


def add_lezioni_menu_item(apps, schema_editor):
    MenuItem = apps.get_model('documenti', 'MenuItem')
    corsi_menu, _ = MenuItem.objects.get_or_create(
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
        label='Lezioni del mese',
        url_name='corsi:lezioni',
        parent=corsi_menu,
        defaults={
            'icon': 'fa-solid fa-calendar-days',
            'ordine': 1,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0002_menu_item_corsi'),
    ]

    operations = [
        migrations.RunPython(add_lezioni_menu_item, migrations.RunPython.noop),
    ]
