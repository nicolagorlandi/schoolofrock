from django.urls import path, re_path
from . import views
from django.contrib.auth.decorators import login_required
from rest_framework import routers
from documenti.views import getOrderFromWEB,getArticoliFromEmporioOpen,getCodicivaFromEmporioOpen,getCategoriFromEmporioOpen,\
    getMarchiArFromEmporioOpen,getUnitaFromEmporioOpen,getGrmemastFromEmporioOpen,getGrmedettFromEmporioOpen,getArt_linkFromEmporioOpen,\
    getClientiFromEmporioOpen,getCausmagaFromEmporioOpen,getDocTipBaFromEmporioOpen,getCausdocuFromEmporioOpen,\
    view_cart,add_to_cart,remove_from_cart,cartItemsSelection,fromCartToOrder,ArticoliAutocomplete,\
    CreateDocumentoView,nominativi_autocomplete,upload_file

router = routers.DefaultRouter()
router.register(r'getOrderFromWEB', getOrderFromWEB, basename='getOrderFromWEB')
router.register(r'getArticoliFromEmporioOpen', getArticoliFromEmporioOpen, basename='getArticoliFromEmporioOpen')
router.register(r'getCodicivaFromEmporioOpen', getCodicivaFromEmporioOpen, basename='getCodicivaFromEmporioOpen')
router.register(r'getCategoriFromEmporioOpen', getCategoriFromEmporioOpen, basename='getCategoriFromEmporioOpen')
router.register(r'getMarchiArFromEmporioOpen', getMarchiArFromEmporioOpen, basename='getMarchiArFromEmporioOpen')
router.register(r'getUnitaFromEmporioOpen', getUnitaFromEmporioOpen, basename='getUnitaFromEmporioOpen')
router.register(r'getGrmemastFromEmporioOpen', getGrmemastFromEmporioOpen, basename='getGrmemastFromEmporioOpen')
router.register(r'getGrmedettFromEmporioOpen', getGrmedettFromEmporioOpen, basename='getGrmedettFromEmporioOpen')
router.register(r'getArt_linkFromEmporioOpen', getArt_linkFromEmporioOpen, basename='getArt_linkFromEmporioOpen')
router.register(r'getClientiFromEmporioOpen', getClientiFromEmporioOpen, basename='getClientiFromEmporioOpen')
router.register(r'getCausmagaFromEmporioOpen', getCausmagaFromEmporioOpen, basename='getCausmagaFromEmporioOpen')
router.register(r'getDocTipBaFromEmporioOpen', getDocTipBaFromEmporioOpen, basename='getDocTipBaFromEmporioOpen')
router.register(r'getCausdocuFromEmporioOpen', getCausdocuFromEmporioOpen, basename='getCausdocuFromEmporioOpen')



urlpatterns = router.urls+[
path('login',views.login, name='login'),
path('logout',views.logout, name='logout'),
path('dashboard',views.dashboard, name='dashboard'),


path('products',login_required(views.products.as_view()), name='products'),
path('addArticolo/', login_required(views.Articoli_add.as_view()), name='add_Articolo'),  
path('<str:pk>/editArticolo/', login_required(views.Articoli_edit.as_view()), name='edit_Articolo'),    
path('<str:articolo_id>/deleteArticolo/',login_required(views.Articolo_delete), name='delete_Articolo'),   

path('clienti',login_required(views.clienti), name='clienti'),
path('fornitori',login_required(views.fornitori), name='fornitori'),
path('addCliente/<slug:tipo>/', login_required(views.Clienti_add.as_view()), name='add_Cliente'),  
path('editCliente/<slug:tipo>/<str:pk>/', login_required(views.Clienti_edit.as_view()), name='edit_Cliente'),    
path('deleteCliente/<slug:tipo>/<str:pk>/',login_required(views.Clienti_delete), name='delete_Cliente'),   

path('<str:causale>/documenti',views.documenti, name='documenti'),
path('<str:causaleSelezionata>/addordine/', login_required(views.CreateDocumentoView.as_view()), name='add_ordine'), 
path('<int:order_id>/editordine/', login_required(views.UpdateDocumentoView.as_view()), name='edit_ordine'), 
path('<int:order_id>/deleteordine/', login_required(views.deleteOrdine), name='delete_ordine'),
path('<int:order_id>/evade_ordine/', login_required(views.evadeOrdine), name='evade_ordine'),
path('<str:causaleSelezionata>/<str:gruppoSelezionato>/caricaordine/', login_required(views.formset_Articoli), name='carica_Ordine'),

path('cartItemSelection/',login_required(views.cartItemsSelection.as_view()), name='cartItemsSelection'),
path('cart/', login_required(views.view_cart), name='view_cart'),
path('add', login_required(views.add_to_cart), name='add_to_cart'),
path('remove/<str:id>/', login_required(views.remove_from_cart), name='remove_from_cart'),
path('fromCartToOrder/', login_required(views.fromCartToOrder), name='fromCartToOrder'),
path('uploadDeskTooCSV/', login_required(views.upload_file), name='uploadDeskTooCSV'),
path("stampaDocumento/<int:pk>/", views.ordine_pdf, name="stampaDocumento"),

# lettura dati articoli cambio articoli dettaglio documenti.
re_path(r'^ajax/leggiPrezzoDescrizioneArticolo/$', views.leggiPrezzoDescrizioneArticolo, name='leggiPrezzoDescrizioneArticolo'),
re_path(r'^ajax/leggiintestatario/$', views.leggiintestatario, name='leggiintestatario'),
# auto completamento articoli
re_path(r'^articoli-autocomplete/$', ArticoliAutocomplete.as_view(), name='articoli-autocomplete'),
 
# auto completamento nominativi
re_path(r'^nominativi-autocomplete/$', nominativi_autocomplete.as_view(), name='nominativi-autocomplete'),


]

