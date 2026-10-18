from django.urls import path

from . import views

app_name = 'corsi'

urlpatterns = [
    path('', views.elenco_corsi, name='elenco'),
    path('lezioni/', views.gestione_lezioni, name='lezioni'),
    path(
        'lezioni/calendario/',
        views.calendario_lezioni,
        name='calendario-lezioni',
    ),
    path(
        'lezioni/presenze-mensili/',
        views.presenze_mensili,
        name='presenze-mensili',
    ),
    path(
        'fatturazione/',
        views.fatturazione_mensile,
        name='fatturazione',
    ),
    path(
        'fatturazione/<str:alunno_id>/genera/',
        views.genera_ricevuta_alunno,
        name='genera-ricevuta',
    ),
    path(
        'fatturazione/genera-tutte/',
        views.genera_tutte_ricevute,
        name='genera-tutte-ricevute',
    ),
    path(
        'lezioni/eventi/',
        views.eventi_calendario,
        name='calendario-eventi',
    ),
    path(
        'lezioni/<int:pk>/presenza/',
        views.aggiorna_presenza_lezione,
        name='aggiorna-presenza',
    ),
    path(
        'lezioni/<int:pk>/modifica-orario/',
        views.modifica_orario_lezione,
        name='modifica-orario-lezione',
    ),
    path('nuovo/', views.CorsoCreateView.as_view(), name='nuovo'),
    path('<int:pk>/duplica/', views.duplica_corso, name='duplica'),
    path('<int:pk>/modifica/', views.CorsoUpdateView.as_view(), name='modifica'),
    path('<int:pk>/elimina/', views.CorsoDeleteView.as_view(), name='elimina'),
    path(
        'autocomplete/insegnanti/',
        views.InsegnantiAutocomplete.as_view(),
        name='insegnante-autocomplete',
    ),
    path(
        'autocomplete/alunni/',
        views.AlunniAutocomplete.as_view(),
        name='alunno-autocomplete',
    ),
]
