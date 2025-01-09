from django import forms
from django.contrib.auth.models import User
from django.forms import FileField, Form, TextInput, widgets
from .models import *
from django.utils.translation import gettext as _
from django.forms import ModelForm, Textarea
from django.forms import BaseInlineFormSet
from django.forms.models import modelformset_factory
from bootstrap_datepicker_plus.widgets import DatePickerInput
from dal import autocomplete

# classe per la selezione della data.
class DateInput( forms.DateInput ):
    input_type='date'
    
    def __init__(self, **kwargs):
        kwargs["format"] = "%Y-%m-%d"
        super().__init__(**kwargs)    


class UserLoginForm(forms.ModelForm):
    username = forms.CharField(
                            widget=forms.TextInput(attrs={'id': 'floatingInput', 'class': 'form-control mb-3'}),
                            required=True)
    password = forms.CharField(
                            widget=forms.PasswordInput(attrs={'id': 'floatingPassword', 'class': 'form-control mb-3'}),
                            required=True)

    class Meta:
        model=User
        fields=['username','password']

# form per editing clienti
class ClientForm(forms.ModelForm):
    class Meta:
        model = Nominativi     
        fields=['NOCODICE','NOCOGNOM','NO_NOME','NORAGSOC','NOTELEF1','NO_EMAIL']
        labels = {
            'NOCODICE': _('Codice'),
            'NOCOGNOM': _('Cognome'),
            'NO_NOME': _('Nome'),
            'NORAGSOC': _('Descrizione'),
            'NOTELEF1': _('Telefono'),
            'NO_EMAIL': _('E-Mail'),
        }

# form per il caricamento veloce di un ordine (quindi codice nominativo opzionale)
class FastClientForm(forms.ModelForm):
    class Meta:
        model = Nominativi     
        fields=['NOCODICE','NOCOGNOM','NO_NOME','NORAGSOC','NOTELEF1','NO_EMAIL']
        labels = {
            'NOCODICE': _('Nominativo'),
            'NOCOGNOM': _('Cognome'),
            'NO_NOME': _('Nome'),
            'NORAGSOC': _('Descrizione'),
            'NOTELEF1': _('Telefono'),
            'NO_EMAIL': _('E-Mail'),
        }


class ArticoliForm(forms.ModelForm):
    class Meta:
        model = Articoli     
        fields = '__all__'
        
        labels = {
            'ARCODICE': _('Codice'),            
            'ARDESCRI': _('Descrizione'),
            'ARDESSUP': _('Descrizione supplementare'),
            'ARPREZZO': _('Prezzo'),
            'ARCODIVA': _('Codice IVA'),
            'AR_COSTO': _('Costo'),
            'ARCODCAT':_('Categoria'),
            'ARBARCOD':_('Barcode'),
            'ARBARCO2':_('Barcode 2'),
            'ARBARCO3':_('Barcode3'),
            'ARCODUNI':_('Unità di misura')            
        } 

    # per motivi di velocita impostata la ricerca solo sui primi 5 record!
    ARCODGRU = forms.ModelChoiceField(label=_('Gruppo'),queryset=Grmemast.objects.all()[:5], empty_label="",
                                        widget=forms.Select(attrs={
                                            'class': "form-select text-center fw-bold",
                                            'style': 'max-width: auto;',
                                        }))   

    ARCODSGR = forms.ModelChoiceField(label=_('Sotto Gruppo'),queryset=Grmedett.objects.all()[:5], empty_label="",
                                        widget=forms.Select(attrs={
                                            'class': "form-select text-center fw-bold",
                                            'style': 'max-width: auto;',
                                        }))                
    
    ARCODMAR = forms.ModelChoiceField(label=_('Marca'),queryset=Marchiar.objects.all()[:5], empty_label="",
                                        widget=forms.Select(attrs={
                                            'class': "form-select text-center fw-bold",
                                            'style': 'max-width: auto;',
                                        }))             
# caricamento ordini!
class creaOrdineForm(ModelForm):

    class Meta:
        model = Ord_Mast        
        fields = ['DONUMORD','DOALFORD','DODATORD','DOCODINT','DOCODCAU','DOCODUTE','DONOTE','SYNC_UPDATE']
        widgets = {
            'DONOTE': Textarea(attrs={ 'rows': 2}),
            'DODATORD':DateInput,
            'DOCODINT': autocomplete.ModelSelect2(
                            url='nominativi-autocomplete',
                            attrs={
                                # Set some placeholder
                                'data-placeholder': 'Autocomplete ...',
                                # Only trigger autocompletion after 3 characters have been typed
                                'data-minimum-input-length': 3,
                                # La select2 ha nel css line-height: 28px; in select2.css riga 134
                                'style':"line-height: 0px;"
                            }),     
        }    
        labels = {
            'DONUMORD': _('Numero'),  
            'DOALFORD': _('Serie'),   
            'DODATORD': _('Data'),    
            'DOCODINT': _('Intestatario'),                 
            'DOCODCAU': _('Causale'),                 
            'DOCODUTE': _('Operatore'),
            'DONOTE': _('Note'),
            'TotaleDocumento': _('Totale'),
            'SYNC_UPDATE':_('Inviato'),
        }                       
        
    def __init__(self, *args, **kwargs):
        super(creaOrdineForm, self).__init__(*args, **kwargs)
        self.fields["DOCODUTE"].disabled=True
        self.fields["DOCODCAU"].disabled=True  
        
# dettaglio riga documento
class creaDettaglioOrdineForm(ModelForm):

    class Meta:
        model = Ord_dett        
        fields = ['DOCODART','DOQTAUM1','DOPREZZO','DODESART','DODESSUP']
        labels={
                'DOCODART':  '',                            
                'DOQTAUM1':  '',
                'DOPREZZO':  '',
                'DODESART':  '',                
                'DODESSUP':  '',

        }
        widgets = {
            "DOQTAUM1": forms.NumberInput(attrs={'step': 1,'decimal_places' : 2,"class":"form-control form-control-sm text-end "}),
            "DOPREZZO": forms.NumberInput(attrs={'step': 1,'decimal_places' : 2,"class":"form-control form-control-sm -sm text-end"}),
            "DODESART": forms.TextInput(attrs={"class":"form-control form-control-sm "}),  
            'DODESSUP': Textarea(attrs={ 'rows': 1,"class":"form-control form-control-sm "}),
            'DOCODART': autocomplete.ModelSelect2(
                            url='articoli-autocomplete',
                            attrs={
                                # Set some placeholder
                                'data-placeholder': 'Autocomplete ...',
                                # Only trigger autocompletion after 3 characters have been typed
                                'data-minimum-input-length': 3,
                                # Al cambio leggo prezzo e descrizioni dell'articolo!
                                'onchange' : "cambioProdotto(this.value, this);",   
                                # La select2 ha nel css line-height: 28px; in select2.css riga 134
                                'style':"line-height: 0px; width:100%",
                                "class":"form-control form-control-sm "
                            }),

        }   
                    
# import elenco articoli da csv basato su carello da DESKTOO
class UploadFileForm(forms.Form):
    file = forms.FileField()
    # cablato per dare layout bootstrap all'input file
    file.widget.attrs.update({'class': 'form-control form-control-sm '})

# form base per il temporaneo per creare documento a partire dull'elenco degli articoli
class TempArticoliForm(forms.ModelForm): 
    class Meta:
        model = tempdettagliodoc
        fields = ['DOQTAUM1','ARCODICE','ARDESCRI','ARPREZZO','ARDESSUP']       
        widgets = {
            "DOQTAUM1": forms.NumberInput(attrs={'step': 1,'decimal_places' : 0, 'labels':False}),
            "ARPREZZO": forms.NumberInput(attrs={'step': 1,'decimal_places' : 2}), 
            'ARDESSUP': Textarea(attrs={ 'rows': 1}),
            }        
        labels = {
            'DOQTAUM1': '', 
            'ARCODICE': '', 
            'ARDESCRI': '', 
            'ARDESSUP': '', 
            'ARPREZZO': '', 
        }   

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # disabilito tutto tranne prezzo e quantità
        # self.fields["ARCODICE"].disabled = True               
        #self.fields["ARDESCRI"].disabled = True         
        #self.fields["ARDESSUP"].disabled = True


                     