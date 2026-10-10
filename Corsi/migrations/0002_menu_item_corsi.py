from django.db import migrations


def add_corsi_menu_item(apps, schema_editor):
    MenuItem = apps.get_model('documenti', 'MenuItem')
    MenuItem.objects.get_or_create(
        label='Corsi',
        url_name='corsi:elenco',
        parent=None,
        defaults={
            'icon': 'fa-solid fa-graduation-cap',
            'ordine': 3,
            'visible': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0001_initial'),
        ('documenti', '0007_ord_mast_dotipdoc'),
    ]

    operations = [
        migrations.RunPython(add_corsi_menu_item, migrations.RunPython.noop),
    ]
