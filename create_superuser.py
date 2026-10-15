import os
import django

# Imposta le variabili necessarie per usare Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PaNet1Project.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL")

if not username or not password or not email:
    print("Variabili superuser mancanti, nessun utente creato.")
else:
    if User.objects.filter(username=username).exists():
        print(f"Superuser '{username}' già esistente, non lo creo.")
    else:
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"Superuser '{username}' creato con successo.")
