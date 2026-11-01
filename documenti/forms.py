from django import forms
from django.contrib.auth.models import User
from django.forms import FileField, Form, TextInput, ValidationError, widgets
from .models import *
from django.utils.translation import gettext as _
from django.forms import ModelForm, Textarea
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.forms.models import modelformset_factory
from bootstrap_datepicker_plus.widgets import DatePickerInput
from dal import autocomplete
from django.template.defaultfilters import slugify

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
        fields=['NOCODICE','NOCOGNOM','NO_NOME','NORAGSOC','NOTELEF1','NO_EMAIL','NOINDIRI',
                'NONUMCIV',
                'NO_CITTA',
                'NOPROVIN',
                'NOINDCAP',
                'NOPARIVA',
                'NOCODFIS',
                'NONAZION',
                'NONOMPEC',
                'NOCODSDI',
                'NORITPIM',
                'NORITPER',
                'NOCASSA',
                'NOCODIVA']
        labels = {
            'NOCODICE': _('Codice'),
            'NOCOGNOM': _('Cognome'),
            'NO_NOME': _('Nome'),
            'NORAGSOC': _('Descrizione'),
            'NOTELEF1': _('Telefono'),
            'NO_EMAIL': _('E-Mail'),
            'NOINDIRI':_('Indirizzo'),
            'NONUMCIV':_('Civico'),
            'NO_CITTA':_('Citta'),
            'NOPROVIN':_('Provincia'),
            'NOINDCAP':_('CAP'),
            'NOPARIVA':_('P.IVA'),
            'NOCODFIS':_('Codice Fiscale'),
            'NONAZION':_('Nazione'),
            'NONOMPEC':_('PEC'),
            'NOCODSDI':_('SDI'),
            'NORITPIM':_('% Base Imp.Ritenuta'),
            'NORITPER':_('% Ritenuta Acconto'),
            'NOCASSA':_('Cassa(%)'),
            'NOCODIVA':_('Codice IVA'),          
        }


    def __init__(self, *args, **kwargs):
        self.tipo = kwargs.pop('tipo', None)
        super().__init__(*args, **kwargs)

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


class CausdocuForm(forms.ModelForm):
    class Meta:
        model = Causdocu
        fields = [
            'CDCODICE',
            'CDDESCRI',
            'CD_CICLO',
            'CDTIPDOC',
            'CDTIPINT',
            'CDCAUMAG',
            'CDPAGDEF',
            'CDNUMAUT',
            'CDQUALIT',
            'CDINTOBB',
            'CDGESIVA',
            'CDGESPAG',
        ]
        labels = {
            'CDCODICE': _('Codice'),
            'CDDESCRI': _('Descrizione'),
            'CD_CICLO': _('Ciclo'),
            'CDTIPDOC': _('Tipo documento'),
            'CDTIPINT': _('Tipo intestatario'),
            'CDCAUMAG': _('Causale di magazzino'),
            'CDPAGDEF': _('Pagamento predefinito'),
            'CDNUMAUT': _('Numerazione automatica'),
            'CDQUALIT': _('Qualità'),
            'CDINTOBB': _('Intestatario obbligatorio'),
            'CDGESIVA': _('Gestione IVA'),
            'CDGESPAG': _('Gestione pagamenti'),
        }

    def save(self, commit=True):
        if not self.instance.slug:
            self.instance.slug = slugify(self.instance.CDCODICE)
        return super().save(commit=commit)


    # per motivi di velocita impostata la ricerca solo sui primi 5 record!
    ARCODGRU = forms.ModelChoiceField(label=_('Gruppo'),queryset=Grmemast.objects.all()[:5], 
                                        empty_label="",
                                        required=False,
                                        widget=forms.Select(attrs={
                                            'class': "form-select text-center fw-bold",
                                            'style': 'max-width: auto;',
                                        }))   

    ARCODSGR = forms.ModelChoiceField(label=_('Sotto Gruppo'),queryset=Grmedett.objects.all()[:5], 
                                        empty_label="",
                                        required=False,
                                        widget=forms.Select(attrs={
                                            'class': "form-select text-center fw-bold",
                                            'style': 'max-width: auto;',
                                        }))                
    
    ARCODMAR = forms.ModelChoiceField(label=_('Marca'),queryset=Marchiar.objects.all()[:5], 
                                        empty_label="",
                                        required=False,
                                        widget=forms.Select(attrs={
                                            'class': "form-select text-center fw-bold",
                                            'style': 'max-width: auto;',
                                        }))             


class PagamentiForm(forms.ModelForm):
    class Meta:
        model = PAGAMENTI
        fields = ['PACODICE', 'PADESCRI', 'PADESEAS']
        labels = {
            'PACODICE': _('Codice'),
            'PADESCRI': _('Descrizione'),
            'PADESEAS': _('Descrizione per TeamSystem'),
        }


class PagamentiDettaglioForm(forms.ModelForm):
    class Meta:
        model = PAG_DETT
        fields = [
            'PDNUMSCA',
            'PDGIORNO',
            'PDINTERV',
            'PDPERCEN',
            'PDTIPPAG',
            'PDPAGATA',
            'PD_FISSO',
        ]
        labels = {
            'PDNUMSCA': _('Numero rata'),
            'PDGIORNO': _('Decorrenza'),
            'PDINTERV': _('Intervallo (mesi)'),
            'PDPERCEN': _('Percentuale'),
            'PDTIPPAG': _('Tipo pagamento'),
            'PDPAGATA': _('Pagata'),
            'PD_FISSO': _('Giorno del mese'),
        }
        widgets = {
            'PDNUMSCA': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'PDINTERV': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'PDPERCEN': forms.NumberInput(
                attrs={'min': '0', 'step': '0.0001'}
            ),
            'PDPAGATA': forms.Select(
                choices=[('N', _('No')), ('S', _('Sì'))],
            ),
            'PD_FISSO': forms.NumberInput(attrs={'min': '0', 'max': '31'}),
        }


PagamentiDettaglioFormSet = inlineformset_factory(
    PAGAMENTI,
    PAG_DETT,
    form=PagamentiDettaglioForm,
    extra=0,
    can_delete=True,
)


# caricamento ordini!
class creaOrdineForm(ModelForm):
    DOTIPDOC = forms.CharField(
        required=False,
        disabled=True,
        widget=forms.HiddenInput(),
    )


    def __init__(self, *args, TipoDocumentoSelezionato=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['DORITACC'].disabled = True
        self.fields['DOCODUTE'].disabled = True
        if (
            not self.is_bound
            and self.instance.DOTCOIVA_id is None
            and self.instance.DOCODINT_id is not None
            and self.instance.DOCODINT.NOCODIVA_id is not None
        ):
            self.initial['DOTCOIVA'] = self.instance.DOCODINT.NOCODIVA
        if TipoDocumentoSelezionato:
            self.fields["DOCODCAU"].queryset = Causdocu.objects.filter(
                CDTIPDOC=TipoDocumentoSelezionato
            )

    def clean(self):
        cleaned_data = super().clean()
        intestatario = cleaned_data.get('DOCODINT')
        if (
            cleaned_data.get('DOTCOIVA') is None
            and intestatario is not None
            and intestatario.NOCODIVA_id is not None
        ):
            cleaned_data['DOTCOIVA'] = intestatario.NOCODIVA
        return cleaned_data

    class Meta:
        model = Ord_Mast        
        fields = ['DONUMORD','DOALFORD','DODATORD','DOCODINT','DOCODCAU','DOCODUTE','DONOTE','SYNC_UPDATE','DOCODPAG','DO_CASSA','DORITPIM','DORITPER','DORITACC','DOTIPDOC','DOTCOIVA']
        labels = {
            'DONUMORD': _('Numero'),
            'DOALFORD': _('Serie'),
            'DODATORD': _('Data'),
            'DOCODINT': _('Intestatario'),
            'DOCODCAU': _('Causale'),
            'DOCODUTE': _('Operatore'),
            'DONOTE': _('Note'),
            'TotaleDocumento': _('Totale'),
            'SYNC_UPDATE': _('Inviato'),
            'DOCODPAG': _('Pagamento'),
            'DO_CASSA': _('Percentuale cassa previdenziale'),
            'DORITPIM': _('Percentuale ritenuta su imponibile'),
            'DORITPER': _('Percentuale ritenuta d\'acconto'),
            'DORITACC': _('Importo ritenuta d\'acconto'),
            'DOTCOIVA': _('Codice IVA'),
        }
        widgets = {
            'DONOTE': Textarea(attrs={ 'rows': 2}),
            'DODATORD':DateInput,
            'DORITPIM': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'DORITPER': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'DO_CASSA': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'DORITACC': forms.NumberInput(attrs={'readonly': 'readonly'}),
            'DOCODINT': autocomplete.ModelSelect2(
                            url='nominativi-autocompleteform',
                            forward=['DOCODCAU'],
                            attrs={
                                # Set some placeholder
                                'data-placeholder': 'Autocomplete ...',
                                # Only trigger autocompletion after 3 characters have been typed
                                'data-minimum-input-length': 3,
                                # La select2 ha nel css line-height: 28px; in select2.css riga 134
                                'style':"line-height: 0px;"
                            }),     
        }    
        widget=forms.Select(attrs={"class": "form-select select2-intestatario"})
        DOCODCAU = forms.ModelChoiceField(label=_('Causale'),queryset=Causdocu.objects.none(), 
                                            empty_label="",
                                            required=False,
                                            widget=forms.Select(attrs={
                                                'class': "form-select text-center fw-bold",
                                                'style': 'max-width: auto;',
                                                'onchange': 'cambioCausale(this.value, this)'
                                            }))   

    def clean_DO_CASSA(self):
        if 'DO_CASSA' not in self.data:
            return self.instance.DO_CASSA or 0
        return self.cleaned_data.get('DO_CASSA') or 0
      
# dettaglio riga documento
class creaDettaglioOrdineForm(ModelForm):
    DOCODIVA = forms.ModelChoiceField(
        label=_('Codice IVA'),
        queryset=Codiciva.objects.all().order_by('CICODICE'),
        required=False,
        empty_label='',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    class Meta:
        model = Ord_dett        
        fields = ['DOCODART','DOQTAUM1','DOPREZZO','DODESART','DODESSUP','DOCODIVA']
        labels={
                'DOCODART':  '',                            
                'DOQTAUM1':  '',
                'DOPREZZO':  '',
                'DODESART':  '',                
                'DODESSUP':  '',
                'DOCODIVA': _('Codice IVA'),

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.DOCODIVA_id is None:
            documento = self.instance.DOCODICE
            articolo = self.instance.DOCODART
            codice_iva = (
                documento.DOTCOIVA
                if documento is not None and documento.DOTCOIVA_id is not None
                else articolo.ARCODIVA
                if articolo is not None
                else None
            )
            if codice_iva is not None:
                self.initial['DOCODIVA'] = codice_iva

    def clean_DOCODIVA(self):
        codice_iva = self.cleaned_data.get('DOCODIVA')
        articolo = self.cleaned_data.get('DOCODART')
        documento = self.instance.DOCODICE
        if codice_iva is None and documento is not None and documento.DOTCOIVA_id:
            return documento.DOTCOIVA
        if codice_iva is None and articolo is not None:
            return articolo.ARCODIVA
        return codice_iva

    # se la quantita non è popolato o a zero
    def clean_DOQTAUM1(self):
        q = self.cleaned_data.get("DOQTAUM1")
        if q == 0 or q==None:
            raise ValidationError("La quantità non può essere zero.")
        return q  

# form scadenze
class ScadenzeForm(ModelForm):

    SCTIPPAG = forms.ModelChoiceField(
        label=_('Tipo pagamento'),
        queryset=MODPAGAM.objects.all().order_by('MPCODICE'),
        required=False,
        empty_label='',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    class Meta:
        model = Scadenze
        fields = ['SCNUMSCA', 'SCDATSCA', 'SCIMPSCA', 'SCTIPPAG', 'SCPAGATA', 'SCDATPAG', 'SCNOTE']
        labels = {
            'SCNUMSCA': _('N. rata'),
            'SCDATSCA': _('Scadenza'),
            'SCIMPSCA': _('Importo'),
            'SCTIPPAG': _('Tipo pagamento'),
            'SCPAGATA': _('Pagata'),
            'SCDATPAG': _('Data pagamento'),
            'SCNOTE': _('Note'),
        }
        widgets = {
            'SCDATSCA': DateInput(attrs={'type': 'date'}),
            'SCDATPAG': DateInput(attrs={'type': 'date'}),
            'SCIMPSCA': forms.NumberInput(attrs={'step': 1,'decimal_places' : 2,"class":"form-control form-control-sm -sm text-end"}),
            'SCNOTE': forms.TextInput(),
        }

# dettaglio iva
class RivadettForm(ModelForm):

    RICODIVA = forms.ModelChoiceField(
        label=_('Codice IVA'),
        queryset=Codiciva.objects.all().order_by('CICODICE'),
        required=True,
        empty_label='',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    class Meta:
        model = Rivadett
        fields = ['RICODIVA','RIIMPONI', 'RIIMPOST']
        labels = {
            'RIIMPONI': _('Imponibile'),
            'RIIMPOST': _('Imposta'),
        }
        widgets = {
            'RIIMPONI':forms.NumberInput(attrs={'step': 1,'decimal_places' : 2,"class":"form-control form-control-sm -sm text-end"}),
            'RIIMPOST':forms.NumberInput(attrs={'step': 1,'decimal_places' : 2,"class":"form-control form-control-sm -sm text-end"}),
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


                     