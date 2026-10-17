from django.db import migrations


def add_pagamenti_menu(apps, schema_editor):
    MenuItem = apps.get_model('documenti', 'MenuItem')
    menu_items = MenuItem.objects.using(schema_editor.connection.alias)
    archivi, _ = menu_items.get_or_create(
        label='Archivi',
        parent=None,
        defaults={
            'icon': 'fa-solid fa-folder-open',
            'ordine': 0,
            'visible': True,
        },
    )
    menu_items.update_or_create(
        label='Pagamenti',
        parent=archivi,
        defaults={
            'url_name': 'pagamenti-list',
            'tipoDocumento': None,
            'icon': 'fa-solid fa-money-bill',
            'ordine': 5,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('documenti', '0011_menu_cicli_scadenze'),
    ]

    operations = [
        migrations.RunPython(add_pagamenti_menu, migrations.RunPython.noop),
    ]
