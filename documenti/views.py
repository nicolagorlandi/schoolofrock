from csv import DictReader
import csv
import decimal
from io import TextIOWrapper
from msilib.schema import ListView
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from django.contrib.auth.models import User, auth
from django.contrib import messages
from django.views.generic.edit import UpdateView,CreateView
from django.forms import ValidationError, inlineformset_factory
from django.forms import formset_factory,modelformset_factory
from django.views import View, generic

from django.http import JsonResponse,FileResponse,HttpResponse
import re
from django.utils.translation import gettext as _

from django.db import connection,transaction
from django.db.models import Q,F,Sum,Max,Case, When,FloatField,FilteredRelation,Subquery
from django_filters.views import FilterView
from django.core.paginator import Paginator

from rest_framework import generics, serializers, filters
from rest_framework import viewsets, status

from rest_framework_xml.renderers import XMLRenderer
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404

from .models import *
from .forms import *
from .filters import ArticoliFilter, Ord_MastFilter,DashboardFilter
from .cart import Cart
from dal import autocomplete

import logging
import json

logger = logging.getLogger(__name__)

# numero di righe vuote create alla partenza!
ROW_IN_DOC_DETAILS = 10

#Anonymous required
def anonymous_required(function=None, redirect_url=None):

   if not redirect_url:
        redirect_url = 'dashboard'

   actual_decorator = user_passes_test(
       lambda u: u.is_anonymous,
       login_url=redirect_url
   )

   if function:
       return actual_decorator(function)
   return actual_decorator

# @anonymous_required
def login(request):
    context = {}
    if request.method == 'GET':
        form = UserLoginForm()
        context['form'] = form
        return render(request, 'documenti/login.html', context)

    if request.method == 'POST':
        form = UserLoginForm(request.POST)

        username = request.POST['username']
        password = request.POST['password']

        user = auth.authenticate(username=username, password=password)
        if user is not None:
            auth.login(request, user)
            # apro la gestione degli ordini..
            ordVe = Causdocu.objects.filter(CD_CICLO='V').filter(CDTIPDOC='OV')
            if ordVe.exists():
                # per ora prendo il primo poi gestiamo con flag!
                return redirect('documenti',causale=ordVe.first().CDCODICE)
            else:
                return redirect('dashboard')
        else:
            context['form'] = form
            messages.error(request, 'Invalid Credentials')
            return redirect('login')


    return render(request, 'documenti/login.html', context)

@login_required
def clients(request):
    context = {}
    clienti = Nominativi.objects.all()
    context['Nominativi'] = clienti

    if request.method == 'GET':
        form = ClientForm()
        context['form'] = form
        return render(request, 'documenti/clients.html', context)

    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()

            messages.success(request, 'New Client Added')
            return redirect('clients')
        else:
            messages.error(request, 'Problem processing your request')
            return redirect('clients')


    return render(request, 'documenti/clients.html', context)

class Clienti_add(CreateView):
    model = Nominativi 
    template_name = "documenti/cliente.html"
    form_class = ClientForm
    success_url = '/doc/clients'

class Clienti_edit(UpdateView):
    model = Nominativi 
    template_name = "documenti/cliente.html"
    form_class = ClientForm
    success_url = '/doc/clients'
    
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        
        if (Nominativi.objects.filter(NOCODICE=self.object.NOCODICE).count()==0):
            context['Nominativo'] =  None;
        else:
            context['Nominativo'] =  Nominativi.objects.get(NOCODICE=self.object.NOCODICE); 

        return context 
    
    def form_valid(self, form):   
        return super().form_valid(form)  

@login_required
def Clienti_delete(request,pk):
    ricerca = Nominativi.objects.filter(pk=pk)
    if not ricerca.exists():
        # messaggio di errore
        messages.error(request, 'Cliente da eliminare non trovato - prova a ricaricare la pagina')
    else:
        try:
            Nominativi.objects.get(pk=pk).delete()
        except Exception as ex:
            messages.error(request, "Impossibile eliminare Cliente:{}".format(str(ex)))
        finally:
            return redirect('clients')
        
# autocomplete per nominativi basa la ricerca per descrizione e codice
class nominativi_autocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Nominativi.objects.none()

        if self.q:
            return Nominativi.objects.filter(Q(NORAGSOC__icontains=self.q)|Q(NOCODICE__icontains=self.q)).order_by('NOCODICE')[:10]
        else:
            return Nominativi.objects.order_by('NOCODICE')[:10]

# pagina per gestire gli articoli (quindi ricerca, editing, delete, aggiunta)
class products(FilterView):
    template_name = 'documenti/products.html'
    context_object_name = 'articoli'
    paginate_by = 12
    filterset_class = ArticoliFilter

# ritorna all'ultima schermata home (edit contatti)
class RedirectToHomeMixinEditContatti:

    default_redirect = '/'

    def get(self, request, *args, **kwargs):
        if("home" in request.META.get('HTTP_REFERER', self.default_redirect)): 
            request.session['previous_page'] = request.META.get('HTTP_REFERER', self.default_redirect)

        return super().get(request, *args, **kwargs)

    def get_success_url(self):        
        if('previous_page' in self.request.session):
            return self.request.session['previous_page']
        else:
            return super().get_success_url()   

class Articoli_add(CreateView):
    model = Articoli 
    template_name = "documenti/articoli.html"
    form_class = ArticoliForm
    success_url = '/doc/products'

class Articoli_edit(UpdateView):
    model = Articoli 
    template_name = "documenti/articoli.html"
    form_class = ArticoliForm
    success_url = '/doc/products'
    
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        
        if (Articoli.objects.filter(pk=self.object.pk).count()==0):
            context['articolo'] =  None;
        else:
            context['articolo'] =  Articoli.objects.filter(pk=self.object.pk)[0]; 
            context['galleria'] =  Art_link.objects.filter(ALCODART=self.object.pk); 

        return context 
    
    def form_valid(self, form):   
        return super().form_valid(form)  

@login_required
def Articolo_delete(request,articolo_id):
    ricerca = Articoli.objects.filter(pk=articolo_id)
    if not ricerca.exists():
        # messaggio di errore
        messages.error(request, 'Articolo da eliminare non trovato - prova a ricaricare la pagina')
    else:
        try:
            Articoli.objects.get(pk=articolo_id).delete()
        except Exception as ex:
            messages.error(request, "Impossibile eliminare Articolo:{}".format(str(ex)))
        finally:
            return redirect('products')
    

@login_required
def dashboard(request):
    context = {}    
    articoliAMagazzino =Articoli.objects.annotate(
        impegnato=Sum(F('ord_dett__DOIMPEGN')*F('ord_dett__DOQTAUM1')),
        giacenza=Sum(F('ord_dett__DOCARSCA')*F('ord_dett__DOQTAUM1')),
        carico=Sum(Case(When(ord_dett__DOCARSCA=1, then=F('ord_dett__DOQTAUM1')), default=0,output_field=FloatField())),        
        scarico=Sum(Case(When(ord_dett__DOCARSCA=-1, then=F('ord_dett__DOQTAUM1')), default=0,output_field=FloatField())),
        produrre=Sum(F('ord_dett__DOCARSCA')*F('ord_dett__DOQTAUM1'))-Sum(F('ord_dett__DOIMPEGN')*F('ord_dett__DOQTAUM1')),        
        ).filter(~Q(impegnato=0) | ~Q(giacenza=0)| ~Q(scarico=0)| ~Q(carico=0))   


    context['filter'] = DashboardFilter(request.GET, queryset=articoliAMagazzino)
    return render(request, 'documenti/dashboard.html', context)

@login_required
def logout(request):
    auth.logout(request)
    return redirect('login')

@login_required
def documenti(request, causale):
    context = {}
    ord_mast = Ord_Mast.objects.filter(DOCODCAU=causale)
    context['causaleSelezionata'] = causale    
    context['descrizioneCausale'] = Causdocu.objects.get(CDCODICE=causale).CDDESCRI
    context['filter'] = Ord_MastFilter(request.GET, queryset=ord_mast)
    # aggiungo i gruppi per i pulsanti di apertura
    context['gruppi'] = Grmemast.objects.filter(GRCARRAP=1).order_by('-GRDESCRI')

    return render(request, 'documenti/documenti.html', context)  
    

# gestione elenco articoli da caricare (carica rapido)
def formset_Articoli(request,causaleSelezionata, gruppoSelezionato):

    with connection.cursor() as cursor:
        cursor.execute("""CREATE temporary table documenti_tempdettagliodoc AS 
                        SELECT ARCODICE,ARDESCRI,ARDESSUP,ARPREZZO, 0 AS DOQTAUM1 FROM documenti_articoli 
                         Where ARCODGRU_id = '"""+gruppoSelezionato+"';")        
        # modello per gli articoli da caricare.
        TempArticoliFormSet = modelformset_factory(tempdettagliodoc, 
                                            form=TempArticoliForm,
                                            fields=["DOQTAUM1","ARCODICE","ARDESCRI","ARPREZZO","ARDESSUP"],
                                            extra=0,
                                            can_delete=False,
                                            can_order=False,
                                            )   
        # elenco clienti
        form_nominativo = FastClientForm(request.POST or None)
        # cliente vuoto

        if request.method == "POST":
            formset = TempArticoliFormSet(
                request.POST           
            )
            if formset.is_valid():
                formset.save()

                conta = tempdettagliodoc.objects.filter(DOQTAUM1__gt=0).count();
                if conta > 0:

                    # verifico quale intestatario mettere nel documento
                    intestatario=None
                    if(form_nominativo.is_valid):    
                        # se ho dei dati confermo l'intestatario,se non lo trovo lo creo..                    
                        cognome = request.POST['NOCOGNOM']
                        nome = request.POST['NO_NOME']
                        numTel = request.POST['NOTELEF1']
                        eMAil = request.POST['NO_EMAIL']
                        nocodice = request.POST['NOCODICE']
                        # se ho ragione sociale o numero di telefono ricerco per quelli...
                        if(not nocodice):                        
                            if not(cognome is None or not cognome) or not(nome is None or not nome) or not(numTel is None or not numTel)or not(eMAil is None or not eMAil):                
                                filter_params = {}
                                nominativi = None

                                # se ho il telefono cerco per quello..
                                if not(numTel is None or not numTel):                                                                        
                                    filter_params['NOTELEF1'] = numTel
                                    nominativi = Nominativi.objects.filter(**filter_params)
                                
                                # provo con la mail..
                                if (nominativi is None or not nominativi.exists()) and not(eMAil is None or not eMAil):
                                    filter_params = {}
                                    filter_params['NO_EMAIL'] = eMAil
                                    nominativi = Nominativi.objects.filter(**filter_params)                            

                                # se non trovo ne mail ne telefono provo con la descrizione    
                                if (nominativi is None or not nominativi.exists()) and (not(cognome is None or not cognome) or not(nome is None or not nome)):
                                    filter_params = {}
                                    filter_params['NOCOGNOM'] = cognome
                                    filter_params['NO_NOME'] = nome
                                    nominativi = Nominativi.objects.filter(**filter_params)                            

                                if not nominativi is None and nominativi.exists():
                                    # ho trovato qualcosa, recupero il codice
                                    nocodice = nominativi[0].NOCODICE
                                else:
                                    # creo il cliente (non uso la forma poichè qui non ho il codice)
                                    nuovoIntestatario = Nominativi(NOCOGNOM=cognome, NO_NOME=nome,NOTELEF1=numTel,NO_EMAIL=eMAil)
                                    nuovoIntestatario.save()
                                    # recupero il codice a valle del salvataggio
                                    nocodice = nuovoIntestatario.NOCODICE

                                intestatario = Nominativi.objects.get(NOCODICE=nocodice)
                    else:
                        intestatario = Nominativi.objects.get(NOCODICE=nocodice)
                        
                    # creo il documento e lo mostro pre salvataggio!
                    ord_mast_  = Ord_Mast()
                    ord_mast_.DOCODUTE =request.user
                    ord_mast_.DODATORD = timezone.localtime(timezone.now()).date().today()
                    ord_mast_.intestatario = intestatario 
                    # di base la serie è calcolata con l'anno della data.
                    ord_mast_.DOALFORD = str( ord_mast_.DODATORD.year)
                    ord_mast_.DOCODCAU = Causdocu.objects.get(CDCODICE=causaleSelezionata);

                    if intestatario!=None:
                        ord_mast_.DOCODINT = intestatario

                    if not Ord_Mast.objects.filter(DOALFORD =str( ord_mast_.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max'):
                        ord_mast_.DONUMORD = 1
                    else:
                        ord_mast_.DONUMORD = Ord_Mast.objects.filter(DOALFORD = str( ord_mast_.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max')+1

                    ord_mast_.save()

                    codice=ord_mast_.DOCODICE

                    # carico il dettaglio..
                    for rigo in tempdettagliodoc.objects.filter(DOQTAUM1__gt=0):
                        ord_dett_=Ord_dett();
                        ord_dett_.DOCODICE=ord_mast_
                        ord_dett_.DOCODART=Articoli(ARCODICE=rigo.ARCODICE)
                        ord_dett_.DODESART=rigo.ARDESCRI
                        ord_dett_.DOQTAUM1=rigo.DOQTAUM1
                        ord_dett_.DOPREZZO=rigo.ARPREZZO
                        ord_dett_.save()


                    return redirect('/doc/{}/editordine/'.format(codice))   
                else:
                    return redirect('/doc/{}/documenti'.format(causaleSelezionata))  
            else:
                for form in formset:
                    print("Form Error:", form.errors)                
                return render(request, "documenti/caricaDocumento.html", {"formset": formset, "form_nominativo":form_nominativo, "causale":Causdocu.objects.get(CDCODICE=causaleSelezionata)})                    
        else:
            formset = TempArticoliFormSet()
            return render(request, "documenti/caricaDocumento.html", {"formset": formset,  "form_nominativo":form_nominativo, "causale":Causdocu.objects.get(CDCODICE=causaleSelezionata)})

# autocomplete per articoli basa la ricerca per descrizione e codice
class ArticoliAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Articoli.objects.none()

        if self.q:
            return Articoli.objects.filter(Q(ARDESCRI__icontains=self.q)|Q(ARCODICE__icontains=self.q)).order_by('ARCODICE')[:10]
        else:
            return Articoli.objects.order_by('ARCODICE')[:10]

# nuovo documento
class CreateDocumentoView(generic.CreateView):
    model = Ord_Mast
    form_class = creaOrdineForm
    template_name = 'documenti/documenti_edit.html'
    formset_class = inlineformset_factory(
        Ord_Mast,
        Ord_dett,
        form=creaDettaglioOrdineForm,
        fk_name='DOCODICE',        
        extra= 1, # le righe sono aggiunte dinamicamente via javaScript!        
    )

    # alla conferma ritorno all'elenco dei documenti.
    def get_success_url(self):
        return reverse(
            'documenti',
            kwargs={
                'causale': self.object.DOCODCAU.CDCODICE                
            }
        )
    
    # recupero la causale e se il documento è evaso o meno.
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        
        if 'causaleSelezionata' in self.kwargs.keys():
            context['causaleSelezionata'] =   Causdocu.objects.get(CDCODICE=self.kwargs['causaleSelezionata']);     
        else:
            context['causaleSelezionata'] =  None;     

        context['DocumentoEvaso'] =  False;                         
    
        return context     
    

    def get_object(self, **kwargs):
        return Ord_Mast()
    
    def get_initial(self):
        # Get the initial dictionary from the superclass method
        initial = super(generic.CreateView, self).get_initial()
        # Copy the dictionary so we don't accidentally change a mutable dict
        initial = initial.copy()
        
        data = timezone.localtime(timezone.now()).date().today()
        anno = str( data.year)
        initial['DODATORD'] = data
        initial['DOALFORD'] = anno
        initial['DOCODUTE'] =self.request.user
        #ord_mast_.intestatario = contatti.objects.filter( pk= contacts_id)[0] 
        # di base la serie è calcolata con l'anno della data.
        if 'causaleSelezionata' in self.kwargs.keys():
            initial['DOCODCAU'] =   Causdocu.objects.get(CDCODICE=self.kwargs['causaleSelezionata']);          

        if not Ord_Mast.objects.filter(DOALFORD =str( anno)).aggregate(Max('DONUMORD')).get('DONUMORD__max'):
            initial['DONUMORD'] = 1
        else:
            initial['DONUMORD']  = Ord_Mast.objects.filter(DOALFORD = str( anno)).aggregate(Max('DONUMORD')).get('DONUMORD__max')+1
         # etc...
        return initial    
        
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        form = self.get_form()
        if form.is_valid() and self.formset.is_valid():

            # ricalcolo il numero per la concorrenza ( qui va gestita la causale )
            if not Ord_Mast.objects.filter(DOALFORD =str( self.object.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max'):
                self.object.DONUMORD = 1
            else:
                self.object.DONUMORD = Ord_Mast.objects.filter(DOALFORD = str( self.object.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max')+1
    

            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        result = super().form_valid(form)
        self.formset.save()
        return result

    @property
    def formset(self):
        if '_formset' not in self.__dict__:
            setattr(self, '_formset', self.formset_class(
                self.request.POST if self.request.method == 'POST' else None,
                instance=getattr(self, 'object', self.get_object()),
            ))
        return self._formset

# modifica documento
class UpdateDocumentoView(generic.UpdateView):
    model = Ord_Mast
    form_class = creaOrdineForm
    template_name = 'documenti/documenti_edit.html'
    #success_url = reverse_lazy('select2_outside_admin')
    formset_class = inlineformset_factory(
        Ord_Mast,
        Ord_dett,
        form=creaDettaglioOrdineForm,
        fk_name='DOCODICE',        
        extra=0, # le righe sono aggiunte dinamicamente via javaScript!        
    )

    # alla conferma ritorno all'elenco dei documenti.
    def get_success_url(self):
        return reverse(
            'documenti',
            kwargs={
                'causale': self.object.DOCODCAU.CDCODICE                
            }
        )
    
    # recupero la causale e se il documento è evaso o meno.
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        
        if (Ord_Mast.objects.filter(pk=self.object.pk).count()==0):
            context['causaleSelezionata'] =  None;
        else:
            doc = Ord_Mast.objects.get(pk=self.object.pk)
            context['causaleSelezionata'] =  doc.DOCODCAU; 
            context['DocumentoEvaso'] =  doc.DocumentoEvaso; 

        return context     
    

    def get_object(self, **kwargs):
        if 'order_id' in self.kwargs.keys():
            return Ord_Mast.objects.get(pk=self.kwargs['order_id'])
        else:
            return Ord_Mast.objects.none()
        
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        form = self.get_form()
        if form.is_valid() and self.formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        result = super().form_valid(form)
        self.formset.save()
        return result

    @property
    def formset(self):
        if '_formset' not in self.__dict__:
            setattr(self, '_formset', self.formset_class(
                self.request.POST if self.request.method == 'POST' else None,
                instance=getattr(self, 'object', self.get_object()),
            ))
        return self._formset

# legge prezzo e articolo al cambio articolo nel dettaglio documenti
def leggiPrezzoDescrizioneArticolo(request):
    articoloId = request.GET.get('articoloId', None)
    articolo = Articoli.objects.get(pk= articoloId )
    
    # per poter assegnare il valore sui control mi arriva il nome del control del codice articolo. Da quello cerco di valorizzare i dati di riga.
    txt = request.GET.get('name', None)
    # ricerco il numero tra due meno che Ã¨ la notazione di django se un nome di vista fa lo stesso sono fottuto
    if not txt is None:
        txt=re.search('[\s\S]*-[0-9]*-',txt)[0]

    if not articolo is None: 
        data = {
            'ARPREZZO' :articolo.ARPREZZO,
            'ARDESCRI' :articolo.ARDESCRI,
            'ARDESSUP' :articolo.ARDESSUP,
            'prefisso':txt
        }
    else:
        data = {}
        
    return JsonResponse(data)

# elimina documento
def deleteOrdine(request,order_id):
    ord_mast_  = Ord_Mast.objects.filter(pk=order_id)[0]
    casualeSelezionata =  ord_mast_.DOCODCAU.CDCODICE
    try:
        ord_mast_.delete()    
    except Exception as ex:
        messages.error(request, "Impossibile eliminare Documento:{}".format(str(ex)))
    finally:
        return redirect('documenti', casualeSelezionata)
        

# evade documento
def evadeOrdine(request,order_id):
    # recupero il documento...
    ord_mast_  = Ord_Mast.objects.filter(pk=order_id);
    if ord_mast_.exists():
        ord_mast1  = ord_mast_[0]
        casualeSelezionata =  ord_mast1.DOCODCAU.CDCODICE
        # ricerco se nella causali collegate posso evadere..
        cauColl = causdett.objects.filter(CTCADCOL=casualeSelezionata )
        if cauColl.exists():
            # ho trovato delle causali..
            # a disegno se è solo una allora passo a quella altrimenti faccio altro..
            cauCollCodice = cauColl[0].CTCODICE
            # registro il nuovo documento..
            doc= Ord_Mast();
            doc.DOCODINT = ord_mast1.DOCODINT

            doc.DOCODUTE =request.user
            doc.DODATORD = timezone.localtime(timezone.now()).date().today()
            #ord_mast_.intestatario = contatti.objects.filter( pk= contacts_id)[0] 
            # di base la serie è calcolata con l'anno della data.
            doc.DOALFORD = str( doc.DODATORD.year)
            doc.DOCODCAU = cauCollCodice      

            # ricalcolo il numero per la concorrenza ( qui va gestita la causale )
            if not Ord_Mast.objects.filter(DOALFORD =str( doc.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max'):
                doc.DONUMORD = 1
            else:
                doc.DONUMORD = Ord_Mast.objects.filter(DOALFORD = str( doc.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max')+1
    
            doc.save()
            # ricerco le righe del documento da evadere..
            ord_dettList = Ord_dett.objects.filter(DOCODICE=order_id)
            for item in ord_dettList.iterator():
                ord_dett= Ord_dett()
                ord_dett.DOCODICE = doc
                ord_dett.DOCODART = item.DOCODART
                ord_dett.DODESART = item.DODESART
                ord_dett.DODESSUP = item.DODESSUP
                ord_dett.DOQTAUM1 = item.DOQTAUM1
                ord_dett.DOPREZZO = item.DOPREZZO
                ord_dett.DOCODRIF = item
                
                ord_dett.save()
                # spunto il check evaso del doc di origine..
                item.DOFLEVAS = 1
                item.save()
        else:
            messages.error(request, "Impossibile evadere documento: non impostata causale di evasione per causale {}".format(casualeSelezionata))
        return redirect('documenti', casualeSelezionata)

# riceve in formato Json l'elenco dei codici IVA da Emporio Open
class getCodicivaFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getCodicivaFromEmporioOpen: Ricezione Codici IVA da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            cicodice=item["cicodice"]
                            cidescri=item["cidescri"]
                            ciperiva=item["ciperiva"]
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Codiciva(CICODICE=cicodice,CIDESCRI=cidescri,CIPERIVA=ciperiva )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Codici IVA creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Codice IVA ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Codici IVA su Web dettaglio errore:[{}], codice IVA:[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# riceve in formato Json l'elenco delle categoria da Emporio Open
class getCategoriFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getCategoriFromEmporioOpen: Ricezione Categorie da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            cacodice=item["cacodice"]
                            cadescri=item["cadescri"]
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Categori(CACODICE=cacodice,CADESCRI=cadescri )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Categorie create {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessuna Categoria ricevuta',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione CAtegorie su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# riceve in formato Json l'elenco die Marchi Articolo da Emporio Open
class getMarchiArFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getMarchiArFromEmporioOpen: Ricezione Marchi Articolo da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            macodice=item["macodice"]
                            madescri=item["madescri"]
                            macodpro=item["macodpro"]
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Marchiar(MACODICE=macodice,MADESCRI=madescri, MACODPRO = get_or_none(Nominativi,NOCODICE=macodpro) )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Marchi Articolo creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Marchio Articolo ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Marchi Articoli su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# unitò di misura
class getUnitaFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getUnitaFromEmporioOpen: Ricezione Unità di misura da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            uncodice=item["uncodice"]
                            umdescri=item["undescri"]
                            unNoqta=item["unNoqta"]
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Unita(UNCODICE=uncodice,UNDESCRI=umdescri, UN_NOQTA=unNoqta )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Unità di misura create {}, modificate {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Unità di misura ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Unità di misura su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Gruppi Merceologici
class getGrmemastFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getGrmemastFromEmporioOpen: Ricezione Gruppi Merceologici da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            grcodice=item["grcodice"]
                            grdescri=item["grdescri"]       
                            grcarrap=item["grcarrap"] 
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Grmemast(GRCODICE=grcodice,GRDESCRI=grdescri,GRCARRAP=grcarrap )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Gruppi Merceologici creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Gruppi Merceologici ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Gruppi Merceologici su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Sotto Gruppi Merceologici
class getGrmedettFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getGrmedettFromEmporioOpen: Ricezione Sotto Gruppi Merceologici da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            grsubgrp=item["grsubgrp"]
                            grcodice=item["grcodice"]                            
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Grmedett(GRSUBGRP=grsubgrp,GRCODICE=grcodice )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Sotto Gruppi Merceologici creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Sotto Gruppi Merceologici ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Sotto Gruppi Merceologici su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Tipi base documenti
class getDocTipBaFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getDocTipBaFromEmporioOpen: Ricezione Tipi base documenti da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            dtcodice = item["dtcodice"]
                            dtdescri = item["dtdescri"]
                            dt_ciclo = item["dtCiclo"]
                            dtordine = item["dtordine"]
                            dtregiva = item["dtregiva"]
                            dtportab = item["dtportab"]                         
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Doctipba(DTCODICE = dtcodice ,DTDESCRI = dtdescri ,\
                                        DT_CICLO = dt_ciclo ,DTORDINE = dtordine ,\
                                        DTREGIVA = dtregiva ,DTPORTAB = dtportab , )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Sotto Tipi base documenti creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Tipi base documenti ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Tipi base documenti su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Causali di Magazzino
class getCausmagaFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getGrmedettFromEmporioOpen: Ricezione Causali di Magazzino da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            cmcodice=item["cmcodice"]  
                            cmdescri=item["cmdescri"]  
                            cmcodcol=item["cmcodcol"]  
                            cmcarsca=item["cmcarsca"]  
                            cmimpegn=item["cmimpegn"]  
                            cmordin =item["cmordin"]  
                            cmriserv=item["cmriserv"]                            
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Causmaga(CMCODICE=cmcodice  ,CMDESCRI=cmdescri  ,CMCODCOL=get_or_none(Causmaga,CMCODICE=cmcodcol)  ,\
                                           CMCARSCA=cmcarsca  ,CMIMPEGN=cmimpegn  ,CMORDIN =cmordin   ,\
                                            CMRISERV=cmriserv  )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Sotto Causali di Magazzino creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Sotto Causali di Magazzino ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Causali di Magazzino su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Causali Documenti
class getCausdocuFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getCausdocuFromEmporioOpen: Ricezione Causali Documenti da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            cdcodice = item["cdcodice"] 
                            cddescri = item["cddescri"] 
                            cd_ciclo = item["cdCiclo"] 
                            cdtipdoc = item["cdtipdoc"] 
                            cdcaumag = item["cdcaumag"]                         
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Causdocu(CDCODICE = cdcodice ,CDDESCRI = cddescri ,CD_CICLO = cd_ciclo ,\
                                           CDTIPDOC = cdtipdoc ,CDCAUMAG = get_or_none(Causmaga,CMCODICE=cdcaumag)  )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Sotto Causali di Magazzino creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Sotto Causali di Magazzino ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Causali di Magazzino su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# funzione di servizio per l'import se il dato non è trovao mette None
def get_or_none(classmodel, **kwargs):
    try:
        return classmodel.objects.get(**kwargs)
    except classmodel.MultipleObjectsReturned as e:
        print('ERR====>', e)

    except classmodel.DoesNotExist:
        return None


# riceve in formato Json l'elenco degli articoli da Emporio Open
# riceve i contatti da Thunderbird e li salva nella cartella
class getArticoliFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getArticoliFromEmporioOpen: Ricezione Articoli da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            arcodice=item["arcodice"]
                            ardescri=item["ardescri"]
                            arcodiva=item["arcodiva"]
                            arcodgru=item["arcodgru"]
                            ardessup=item["ardessup"]
                            arprezzo=item["arprezzo"]
                            arcosto=item["arCosto"] #json elimina _ ?
                            arcodcat=item["arcodcat"]                            
                            arcodsgr=item["arcodsgr"]
                            arcodmar=item["arcodmar"]
                            arbarcod=item["arbarcod"]
                            arbarco2=item["arbarco2"]
                            arbarco3=item["arbarco3"]
                            arcoduni=item["arcoduni"]
                            arlotmin=item["arlotmin"]

                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Articoli(ARCODICE=arcodice,
                                           ARDESCRI=ardescri,                                            
                                           ARCODIVA = get_or_none(Codiciva,CICODICE=arcodiva),
                                           ARCODGRU = get_or_none(Grmemast,GRCODICE=arcodgru),
                                           ARDESSUP = ardessup,
                                           ARPREZZO = arprezzo,
                                           AR_COSTO = arcosto,
                                           ARCODCAT = get_or_none(Categori,CACODICE=arcodcat),
                                           ARCODSGR = get_or_none(Grmedett,GRSUBGRP=arcodsgr),
                                           ARCODMAR = get_or_none(Marchiar,MACODICE=arcodmar),
                                           ARBARCOD = arbarcod,
                                           ARBARCO2 = arbarco2,
                                           ARBARCO3 = arbarco3,
                                           ARCODUNI = get_or_none(Unita,UNCODICE=arcoduni),
                                           ARLOTMIN = arlotmin
                                           )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Articoli creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun articolo ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione articoli su Web dettaglio errore:[{}], codice articolo:[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

# Elenco illustrazioni articolo.
class getArt_linkFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getArt_linkFromEmporioOpen: Ricezione Galleria illustrazioni Articoli da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            alcodart=item["alcodart"]
                            arurllnk=item["arurllnk"]                            
                            aldescri=item["aldescri"]                            
                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Art_link(ALCODART=get_or_none(Articoli,ARCODICE=alcodart),ARURLLNK=arurllnk,ALDESCRI=aldescri )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Galleria illustrazioni Articoli creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun  Galleria illustrazioni Articoli ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione  Galleria illustrazioni Articoli su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Clienti
class getClientiFromEmporioOpen(viewsets.ViewSet):

    def create(self, request):
        arcodice='';            
        try:
            # leggo l'array Json di stringhe cin le vcards
            if request.data is not None:                
                logger.info('getClientiFromEmporioOpen: Ricezione Clienti da Emporio Open');

                bcreati = 0;
                bModificati=0;
                try:
                    with transaction.atomic():
                        # scorro gli articoli (se presenti)
                        
                        for item in request.data:
                            # leggo il codice
                            nocodice=item["nocodice"]
                            noragsoc=item["noragsoc"]                            
                            noindiri=item["noindiri"]
                            nonumciv=item["nonumciv"]
                            no_citta=item["noCitta"]
                            noprovin=item["no__pr"]
                            noindcap=item["no_Cap"]
                            notelef1=item["notelef1"]
                            notelef2=item["notelef2"]
                            notelef3=item["notelef3"]
                            no_email=item["noEmail"]
                            nopariva=item["nopariva"]
                            nocodfis=item["nocodfis"]
                            nonotege=item["no_note"]
                            no_nome =item["no_nome"]
                            nocognom=item["nocognom"]                            

                            # Signals nella post_save mi indica se ho creato o meno...
                            obj = Nominativi(NOCODICE=nocodice,NORAGSOC=noragsoc, NOINDIRI=noindiri,\
                                            NONUMCIV=nonumciv,NO_CITTA=no_citta,NOPROVIN=noprovin,NOINDCAP=noindcap,\
                                            NOTELEF1=notelef1,NOTELEF2=notelef2,NOTELEF3=notelef3,NO_EMAIL=no_email,\
                                            NOPARIVA=nopariva,NOCODFIS=nocodfis,NONOTEGE=nonotege,NO_NOME =no_nome ,\
                                            NOCOGNOM=nocognom )
                            obj.save()
                            if (obj.nuovo):
                                bcreati = bcreati+1
                            else:
                                bModificati=bModificati+1
                except Exception:
                    raise 

                if (bModificati>0)or(bcreati>0):
                    return HttpResponse('Clienti creati {}, modificati {}.'.format(bcreati,bModificati),status=status.HTTP_200_OK)
                else:
                    return HttpResponse('Nessun Cliente ricevuto',status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e: # work on python 3.x
            msg ='Errore pubblicazione Clienti su Web dettaglio errore:[{}], codice :[{}]'.format(str(e),arcodice)
            logger.error(msg)
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# manda ordini a Danea        
class getOrderFromWEB(viewsets.ViewSet):

    # senza la create va in errore!
    def create(self, request):
        return None

    def get(self, request):
        try:
            result = FileResponse(generate_DANEAXML(),
                                filename="ordine.xml",
                                as_attachment=True,
                                content_type='application/xml',
                                status=status.HTTP_200_OK,
                                )           
        except Exception as e: # work on python 3.x
            msg ='Errore export documenti verso DANEA :[{}]'.format(str(e))            
            return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)    
        else:           
            # marco i documenti inviati come inviati!
            Ord_Mast.objects.filter(SYNC_UPDATE=1).update(SYNC_UPDATE=0)
        
        if result:
            return result

# genera xml per DANEA        
def generate_DANEAXML() -> bytes:
    content = io.StringIO()
        
    root = ET.Element('EasyfattDocuments', AppVersion='2', Creator='K6 di Nicola Gorlandi' )
    Documents = ET.SubElement(root, 'Documents')

    # ciclo in tutti i documenti con SYNC_UPATE a 1
    results = Ord_Mast.objects.filter(SYNC_UPDATE=1)

    for item in results.iterator():
        # trasformo l'item in xml..
        Document = ET.SubElement(Documents, 'Document')   
        DocumentType = ET.SubElement(Document, 'DocumentType')                   
        # ordine cliente, da mappare sulla causale il tipo per l'export verso Danea ?
        DocumentType.text = 'C'

        Date = ET.SubElement(Document, 'Date')       
        Date.text = item.DODATORD.strftime("%Y-%m-%d")            

        Number = ET.SubElement(Document, 'Number')       
        Number.text = str(item.DONUMORD)

        Numbering = ET.SubElement(Document, 'Numbering')       
        Numbering.text = item.DOALFORD

        if item.DOCODINT:
            CustomerCode = ET.SubElement(Document, 'CustomerCode')                   
            CustomerCode.text = item.DOCODINT.NOCODICE

            CustomerName = ET.SubElement(Document, 'CustomerName')                   
            CustomerName.text = item.DOCODINT.NORAGSOC

            CustomerAddress = ET.SubElement(Document, 'CustomerAddress')                   
            CustomerAddress.text = item.DOCODINT.NOINDIRI

            CustomerPostcode = ET.SubElement(Document, 'CustomerPostcode')                   
            CustomerPostcode.text = item.DOCODINT.NOINDCAP

            CustomerCity = ET.SubElement(Document, 'CustomerCity')                   
            CustomerCity.text = item.DOCODINT.NO_CITTA            

            CustomerProvince = ET.SubElement(Document, 'CustomerProvince')                   
            CustomerProvince.text = item.DOCODINT.NOPROVIN

            CustomerCountry = ET.SubElement(Document, 'CustomerCountry')                   
            CustomerCountry.text = item.DOCODINT.NONAZION

            CustomerFiscalCode = ET.SubElement(Document, 'CustomerFiscalCode')                   
            CustomerFiscalCode.text = item.DOCODINT.NOCODFIS

            CustomerVatCode = ET.SubElement(Document, 'CustomerVatCode')                   
            CustomerVatCode.text = item.DOCODINT.NOPARIVA

            # o PEC o codice SDI
            CustomerEInvoiceDestCode = ET.SubElement(Document, 'CustomerEInvoiceDestCode')
            if not item.DOCODINT.NOCODSDI:                    
                CustomerEInvoiceDestCode.text = item.DOCODINT.NONOMPEC
            else:
                CustomerEInvoiceDestCode.text = item.DOCODINT.NOCODSDI

            CustomerTel = ET.SubElement(Document, 'CustomerTel')                   
            CustomerTel.text = item.DOCODINT.NOTELEF1                

            CustomerCellPhone = ET.SubElement(Document, 'CustomerCellPhone')                   
            CustomerCellPhone.text = item.DOCODINT.NOTELEF2            

            CustomerFax = ET.SubElement(Document, 'CustomerFax')                   
            CustomerFax.text = item.DOCODINT.NOTELEF3                        

            CustomerEmail = ET.SubElement(Document, 'CustomerEmail')                   
            CustomerEmail.text = item.DOCODINT.NO_EMAIL              

            CustomerPec = ET.SubElement(Document, 'CustomerPec')                   
            CustomerPec.text = item.DOCODINT.NONOMPEC                          

        # per ora i prezzi si intendono senza iva (doloriva dovrebbe essere utilizzata qui)
        PricesIncludeVat = ET.SubElement(Document, 'PricesIncludeVat')                   
        PricesIncludeVat.text = 'false'  
        # scorro nelle righe del documento..
        Rows = ET.SubElement(Document, 'Rows')                   
        dettaglio = Ord_dett.objects.filter(DOCODICE=item.pk)

        for rigo in dettaglio.iterator(): 
            Row = ET.SubElement(Rows, 'Row') 

            Code = ET.SubElement(Row, 'Code')                  
            Code.text = rigo.DOCODART.ARCODICE

            Description = ET.SubElement(Row, 'Description')                  
            Description.text = rigo.DODESART

            Qty = ET.SubElement(Row, 'Qty')                  
            Qty.text = str(rigo.DOQTAUM1)

            Um = ET.SubElement(Row, 'Um')      
            if rigo.DOCODART.ARCODUNI:            
                Um.text = rigo.DOCODART.ARCODUNI.UNCODICE

            Price = ET.SubElement(Row, 'Price')                  
            Price.text = str(rigo.DOPREZZO)

            VatCode = ET.SubElement(Row, 'VatCode')                  
            VatCode.text = rigo.DOCODART.ARCODIVA.CICODICE

            Notes = ET.SubElement(Row, 'Notes')                  
            Notes.text = rigo.DODESSUP               
        
    # trasformo in stringa..
    xml_str = ElementTree.tostring(root, xml_declaration = True,encoding='unicode')
    content.write(xml_str)                
    return content.getvalue()


# pagina per la selezione degli articoli da aggiungere al carello
class cartItemsSelection(FilterView):
    template_name = 'documenti/cartItemsSelection.html'
    context_object_name = 'articoli'
    paginate_by = 24
    filterset_class = ArticoliFilter
            
def view_cart(request):
    cart = Cart(request)    
    cart_items = cart.getProducts()
    cart_quants = cart.getQuants()    
    total_price = cart.getCartTotal()    
    return render(request, 'documenti/cart.html', {'cart_items': cart_items, 'quantities':cart_quants, 'total_price': total_price})
 
def add_to_cart(request):
    cart = Cart(request)    
    if request.POST.get('action') == 'post':
        string = request.POST.get('qty')
        try:
            qty = int(string)
            product_id = request.POST.get('arcodice')
            
            articolo = get_object_or_404(Articoli,ARCODICE=product_id)
            cart.add(product=articolo, quantity=qty);

            cart_quantity = cart.count()
            # ritorno la quantità per aggiornare il numero di elementi nel cart
            return JsonResponse({'Totalqty':cart_quantity})            
        except:
            # Handle the exception - no action!
            pass
 
def remove_from_cart(request, id):
    articolo = get_object_or_404(Articoli,ARCODICE=id)
    cart = Cart(request)    
    cart.remove(articolo)
    
    return redirect('view_cart')

# alla conferma del carello salvo in un ordine senza intestatario!
def fromCartToOrder(request):

    try:
        with transaction.atomic():
            cart = Cart(request)    

            # carico la testata dell'ordine, uso la prima causale di ordine di vendita che trovo
            # creo il documento e lo mostro pre salvataggio!
            ord_mast_  = Ord_Mast()
            ord_mast_.DOCODUTE =request.user
            ord_mast_.DODATORD = timezone.localtime(timezone.now()).date().today()
            # di base la serie è calcolata con l'anno della data.
            ord_mast_.DOALFORD = str( ord_mast_.DODATORD.year)
            ord_mast_.DOCODCAU = Causdocu.objects.get(CDTIPDOC='OV');

            if not Ord_Mast.objects.filter(DOALFORD =str( ord_mast_.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max'):
                ord_mast_.DONUMORD = 1
            else:
                ord_mast_.DONUMORD = Ord_Mast.objects.filter(DOALFORD = str( ord_mast_.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max')+1

            ord_mast_.save()

            codice=ord_mast_.DOCODICE

            # carico il dettaglio..
            for keys in cart.cart:    
                ord_dett_=Ord_dett();
                ord_dett_.DOCODICE=ord_mast_
                ord_dett_.DOCODART=Articoli.objects.get(ARCODICE=keys)
                ord_dett_.DODESART=ord_dett_.DOCODART.ARDESCRI
                ord_dett_.DOQTAUM1=cart.cart[keys]
                ord_dett_.DOPREZZO=ord_dett_.DOCODART.ARPREZZO
                ord_dett_.DODESSUP=ord_dett_.DOCODART.ARDESSUP
                ord_dett_.save()

            # svuoto il carrello..
            cart.removeAll();       
        # fuori dalla transazione apro la pagina...
        return redirect('/doc/{}/editordine/'.format(codice))   
    except Exception as e:
        msg ='Errore creando ordine da carrello :[{}]'.format(str(e))            
        return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

def upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # Abbiamo il file da analizzare per produrre il dettaglio dell'ordine di vendita.
            try:
                codice=fromCSVToOrder(request.FILES["file"],request)
                return redirect('/doc/{}/editordine/'.format(codice))  
            except Exception as e: 
                messages.error(request, 'Errore creando ordine da file :[{}]'.format(str(e)) )  
                return render(request, "documenti/uploadFile.html", {"form": form})        
                #return HttpResponse(msg,status=status.HTTP_500_INTERNAL_SERVER_ERROR)  
    else:
        form = UploadFileForm()
        return render(request, "documenti/uploadFile.html", {"form": form})

# dal file CSV crea un nuovo ordine
def fromCSVToOrder(f, request):

    with transaction.atomic():
        bSalva=True
        # carico la testata dell'ordine, uso la prima causale di ordine di vendita che trovo
        # creo il documento e lo mostro pre salvataggio!
        ord_mast_  = Ord_Mast()
        ord_mast_.DOCODUTE =request.user
        ord_mast_.DODATORD = timezone.localtime(timezone.now()).date().today()
        # di base la serie è calcolata con l'anno della data.
        ord_mast_.DOALFORD = str( ord_mast_.DODATORD.year)
        ord_mast_.DOCODCAU = Causdocu.objects.get(CDTIPDOC='OV');

        if not Ord_Mast.objects.filter(DOALFORD =str( ord_mast_.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max'):
            ord_mast_.DONUMORD = 1
        else:
            ord_mast_.DONUMORD = Ord_Mast.objects.filter(DOALFORD = str( ord_mast_.DODATORD.year)).aggregate(Max('DONUMORD')).get('DONUMORD__max')+1

        ord_mast_.save()

        codice=ord_mast_.DOCODICE

        decoded_file = f.read().decode('latin-1').splitlines()
        
        reader = csv.DictReader(decoded_file, delimiter=';')
        for index,row in enumerate(reader):
            # Get each cell value based on key-value pair. 
            # Key will always be what lies on the first row.  
            ord_dett_=Ord_dett();
            ord_dett_.DOCODICE=ord_mast_

            try:
                prz = decimal.Decimal(row['Prezzo di Vendita'].replace(',','.') )
                acq = decimal.Decimal(row['Prezzo di Acquisto'].replace(',','.') )
            except:
                messages.add_message(request,100,'Errore convertendo quantita o prezzo Riga {}, quantita :[{}] prezzo :[{}]  '
                                        .format(str(index),row['Qtà'],row['Prezzo di Vendita']))
                bSalva=False
            
            try:
                articolo = Articoli.objects.get(ARCODICE=row['Codice'])
            except:
                # articolo non trovato lo carico..
                # iva fissa al 22 %
                articolo = Articoli.objects.create(ARCODICE=row['Codice'],ARCODIVA =Codiciva.objects.get(CICODICE='22'),ARDESCRI=row['Nome del prodotto'][:80],ARPREZZO=prz,AR_COSTO=acq)   
                messages.add_message(request,10,'Articolo Riga {} creato :[{}]'.format(str(index),row['Codice']) )
   

            if articolo:
                ord_dett_.DOCODART= articolo
                ord_dett_.DODESART=row['Nome del prodotto'][:80]
                
                # la colonna quantita mette assieme quantita e unita di misura
                # quindi prelevo tutto quello che è a sinistra del primo spazio
                lista = row['Qtà'].split(' ', 1)
                if len(lista)>0:
                    try:
                        ord_dett_.DOQTAUM1=decimal.Decimal(row['Qtà'].split(' ', 1)[0].replace(',','.') )
                        ord_dett_.DOPREZZO=(prz+acq)/2

                        ord_dett_.save()
                    except Exception as e:
                        messages.add_message(request,100,'Errore {} convertendo quantita o prezzo Riga {}, quantita :[{}] prezzo :[{}]  '
                                             .format(repr(e),str(index),row['Qtà'],row['Prezzo di Vendita']))
                        bSalva=False

                else:
                    messages.add_message(request,100,'Errore leggendo la quantita Riga {}, quantita :[{}]'.format(str(index),row['Qtà']))
                    bSalva=False
            else:
                messages.add_message(request,100,'Errore leggendo articolo Riga {}, articolo non trovato :[{}]'.format(str(index),row['Codice']) )
                bSalva=False

        if not bSalva:
            ord_mast_.delete
            raise ValueError('Errore importazione annullata.')    
        # ritorno l'id dell'ordine creato..
        return codice 
