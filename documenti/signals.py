import os

from django.db import DatabaseError, connection
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps

from PaNet1Project import settings

from .models import MenuItem
from django.utils.translation import gettext as _


@receiver(post_migrate)
def create_default_menu(sender, **kwargs):
    # Evita esecuzione per altre app
    if sender.name != "documenti":  
        return

    # --- MENU PRINCIPALE ---

    # Ordini
    ordini, created_ordini = MenuItem.objects.get_or_create(
        label="Ordini",
        parent=None,
        defaults={
            "icon": "fa-solid fa-file-invoice",
            "ordine": 1,
            "visible": True,
        },
    )

    MenuItem.objects.get_or_create(
        label="Lista ordini",
        parent=ordini,
        defaults={
            "icon": "fa-solid fa-list",
            "ordine": 1,
        },
    )

    MenuItem.objects.get_or_create(
        label="Nuovo ordine",
        parent=ordini,
        defaults={
            "icon": "fa-solid fa-plus",
            "ordine": 2,
        },
    )

    # Magazzino
    magazzino, created_magazzino = MenuItem.objects.get_or_create(
        label="Magazzino",
        parent=None,
        defaults={
            "icon": "fa-solid fa-boxes",
            "ordine": 2,
            "visible": True,
        },
    )

    MenuItem.objects.get_or_create(
        label="Articoli",
        parent=magazzino,
        defaults={
            "icon": "fa-solid fa-box",
            "ordine": 1,
        },
    )

    MenuItem.objects.get_or_create(
        label="Giacenze",
        parent=magazzino,
        defaults={
            "icon": "fa-solid fa-warehouse",
            "ordine": 2,
        },
    )

    archivi, created_archivi = MenuItem.objects.get_or_create(
        label="Archivi",
        parent=None,
        defaults={
            "icon": "fa-solid fa-folder-open",
            "ordine": 0,
            "visible": True,
        },
    )
    for label, url_name, ordine in (
        ("Clienti", "clienti", 1),
        ("Fornitori", "fornitori", 2),
        ("Articoli", "products", 3),
    ):
        MenuItem.objects.get_or_create(
            label=label,
            parent=archivi,
            defaults={
                "url_name": url_name,
                "ordine": ordine,
                "visible": True,
            },
        )

    documenti, created_documenti = MenuItem.objects.get_or_create(
        label="Documenti",
        parent=archivi,
        defaults={
            "icon": "fa-solid fa-file-lines",
            "ordine": 4,
            "visible": True,
        },
    )
    MenuItem.objects.get_or_create(
        label="Causali Documenti",
        parent=documenti,
        defaults={
            "url_name": "causali-documenti-list",
            "icon": "fa-solid fa-list",
            "ordine": 1,
            "visible": True,
        },
    )

    MenuItem.objects.get_or_create(
        label="Corsi",
        url_name="corsi:elenco",
        parent=None,
        defaults={
            "icon": "fa-solid fa-graduation-cap",
            "ordine": 3,
            "visible": True,
        },
    )

    print(_("Menù inizializzato automaticamente tramite post_migrate."))


@receiver(post_migrate)
def create_default_CAUSDOCU(sender, **kwargs):

    # Evita esecuzione per altre app
    if sender.name != "documenti":  
        return

    # percorso del file SQL dentro la cartella scripts
    sql_path = os.path.join(settings.BASE_DIR, sender.name, "scriptsDb", "init.sql")

    # se il file non esiste, esci
    if not os.path.exists(sql_path):
        print(f"File SQL non trovato: {sql_path}")
        return

    # esegui lo script SQL
    try:
        # leggi il contenuto del file
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        with connection.cursor() as cursor:
            cursor.execute(sql_script)

        print("[post_migrate] Script SQL eseguito correttamente.")
        #causdett,causdocu,causmaga,codiciva,comuni,doctipba,modpagam,pag_dett,pagament,unita
        print(_("Tabelle base documenti (causdett,causdocu,causmaga,codiciva,comuni,doctipba,modpagam,pag_dett,pagament,unita) popolate automaticamente tramite post_migrate.")) 
    except DatabaseError as e:
        print("⚠️ ERRORE durante l'esecuzione dello script SQL:")
        print(f"   → {e.__class__.__name__}: {e}")
        print("   Lo script è stato interrotto, ma la migrazione continua.")

    except Exception as e:
        print("⚠️ ERRORE GENERICO durante l'esecuzione dello script SQL:")
        print(f"   → {e.__class__.__name__}: {e}")

    
