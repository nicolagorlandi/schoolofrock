from django.db import migrations


def add_corsi_link(apps, schema_editor):
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
    MenuItem.objects.update_or_create(
        label='Corsi',
        url_name='corsi:elenco',
        parent=menu_corsi,
        defaults={
            'icon': 'fa-solid fa-list',
            'ordine': 1,
            'visible': True,
        },
    )
    MenuItem.objects.filter(
        label='Lezioni del mese',
        url_name='corsi:lezioni',
        parent=menu_corsi,
    ).update(ordine=2)


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0003_menu_item_lezioni_del_mese'),
    ]

    operations = [
        migrations.RunPython(add_corsi_link, migrations.RunPython.noop),
    ]
