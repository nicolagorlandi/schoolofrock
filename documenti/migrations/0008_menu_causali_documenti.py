from django.db import migrations


def add_causali_documenti_menu(apps, schema_editor):
    MenuItem = apps.get_model('documenti', 'MenuItem')
    archivio, _ = MenuItem.objects.get_or_create(
        label='Archivi',
        parent=None,
        defaults={
            'icon': 'fa-solid fa-folder-open',
            'ordine': 0,
            'visible': True,
        },
    )
    documenti, _ = MenuItem.objects.update_or_create(
        label='Documenti',
        parent=archivio,
        defaults={
            'url_name': None,
            'tipoDocumento': None,
            'icon': 'fa-solid fa-file-lines',
            'ordine': 4,
            'visible': True,
        },
    )
    MenuItem.objects.update_or_create(
        label='Causali Documenti',
        parent=documenti,
        defaults={
            'url_name': 'causali-documenti-list',
            'tipoDocumento': None,
            'icon': 'fa-solid fa-list',
            'ordine': 1,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('documenti', '0007_ord_mast_dotipdoc'),
    ]

    operations = [
        migrations.RunPython(
            add_causali_documenti_menu,
            migrations.RunPython.noop,
        ),
    ]
