from django.contrib import admin

from .models import Alunno, Corso, Lezioni


admin.site.register(Corso)
admin.site.register(Alunno)
admin.site.register(Lezioni)
