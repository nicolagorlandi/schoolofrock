from django.db import migrations


def add_fatturazione_menu_item(apps, schema_editor):
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
        label='Fatturazione',
        url_name='corsi:fatturazione',
        parent=menu_corsi,
        defaults={
            'icon': 'fa-solid fa-receipt',
            'ordine': 5,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0009_corso_articolo_lezioni_documento_fatturazione'),
        ('documenti', '0007_ord_mast_dotipdoc'),
    ]

    operations = [
        migrations.RunPython(
            add_fatturazione_menu_item,
            migrations.RunPython.noop,
        ),
    ]
