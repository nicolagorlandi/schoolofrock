from django.db import migrations


def add_menu_items(apps, schema_editor):
    MenuItem = apps.get_model("documenti", "MenuItem")
    menu_items = MenuItem.objects.using(schema_editor.connection.alias)

    ciclo_vendite, _ = menu_items.update_or_create(
        label="Ciclo Vendite",
        parent=None,
        defaults={
            "url_name": None,
            "tipoDocumento": "V",
            "icon": "fa-solid fa-circle-up",
            "ordine": 2,
            "visible": True,
        },
    )
    ciclo_acquisti, _ = menu_items.update_or_create(
        label="Ciclo Acquisti",
        parent=None,
        defaults={
            "url_name": None,
            "tipoDocumento": "A",
            "icon": "fa-solid fa-circle-down",
            "ordine": 3,
            "visible": True,
        },
    )
    servizi, _ = menu_items.update_or_create(
        label="Servizi",
        parent=None,
        defaults={
            "url_name": None,
            "tipoDocumento": None,
            "icon": "fa-solid fa-toolbox",
            "ordine": 5,
            "visible": True,
        },
    )

    menu_items.update_or_create(
        label="Logout",
        parent=servizi,
        defaults={
            "url_name": "logout",
            "tipoDocumento": None,
            "icon": "fa-solid fa-arrow-right-from-bracket",
            "ordine": 1,
            "visible": True,
        },
    )
    menu_items.update_or_create(
        label="Scheda Scadenze Attive",
        parent=ciclo_vendite,
        defaults={
            "url_name": "schedascadenzeattive",
            "tipoDocumento": None,
            "icon": "fa-solid fa-money-bill-1",
            "ordine": 0,
            "visible": True,
        },
    )
    menu_items.update_or_create(
        label="Scheda Scadenze Passive",
        parent=ciclo_acquisti,
        defaults={
            "url_name": "schedascadenzepassive",
            "tipoDocumento": None,
            "icon": "fa-solid fa-money-bill-1",
            "ordine": 0,
            "visible": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0010_causdett_unique_ctcodice_ctcadcol"),
    ]

    operations = [
        migrations.RunPython(add_menu_items, migrations.RunPython.noop),
    ]
