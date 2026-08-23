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

    # Evita duplicazioni
    if MenuItem.objects.exists():
        return

    # --- MENU PRINCIPALE ---

    # Ordini
    ordini = MenuItem.objects.create(
        label="Ordini",
        icon="fa-solid fa-file-invoice",
        ordine=1
    )

    MenuItem.objects.create(
        label="Lista ordini",
        #url_name="ordini-list",
        icon="fa-solid fa-list",
        parent=ordini,
        ordine=1
    )

    MenuItem.objects.create(
        label="Nuovo ordine",
        #url_name="ordine-crea",
        icon="fa-solid fa-plus",
        parent=ordini,
        ordine=2
    )

    # Magazzino
    magazzino = MenuItem.objects.create(
        label="Magazzino",
        icon="fa-solid fa-boxes",
        ordine=2
    )

    MenuItem.objects.create(
        label="Articoli",
        #url_name="articoli-list",
        icon="fa-solid fa-box",
        parent=magazzino,
        ordine=1
    )

    MenuItem.objects.create(
        label="Giacenze",
        #url_name="giacenze",
        icon="fa-solid fa-warehouse",
        parent=magazzino,
        ordine=2
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

    

