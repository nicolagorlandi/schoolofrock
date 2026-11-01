from django.db import models
from django.db import transaction
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from datetime import date, time
from uuid import uuid4
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum, Count,Max,Min, F,Aggregate, CharField,OuterRef
from decimal import ROUND_HALF_EVEN, Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
import io
import xml.etree.ElementTree as ET
from xml.etree import ElementTree
from django.core.cache import cache

from PaNet1Project.settings import CCATCLI, CCATFOR
from documenti import funzioni
from .datiRiepilogo import DatiRiepilogo
from .rateizzazione import ElementoRateizzazione, Rateizzazione
from documenti import datiRiepilogo

class MODPAGAM(models.Model):
    MPCODICE = models.CharField(max_length=42,primary_key=True)
    #il primo valore è quello registrato a database, il secondo quello mostrato a video  
    MPTIPPAG= models.CharField(null=True, blank=True, max_length=4,        
        choices=[
            ("",""),
            ("MP01","MP01"),
            ("MP02","MP02"),
            ("MP03","MP03"),
            ("MP04","MP04"),
            ("MP05","MP05"),
            ("MP06","MP06"),
            ("MP07","MP07"),
            ("MP08","MP08"),
            ("MP09","MP09"),
            ("MP10","MP10"),
            ("MP11","MP11"),
            ("MP12","MP12"),
            ("MP13","MP13"),
            ("MP14","MP14"),
            ("MP15","MP15"),
            ("MP16","MP16"),
            ("MP17","MP17"),
            ("MP18","MP18"),
            ("MP19","MP19"),
            ("MP20","MP20"),
            ("MP21","MP21"),
            ("MP22","MP22"),
            ("MP23","MP23")
        ]) # codice pagamento in fattura elettronica

    MPRITACC = models.IntegerField(null=True, blank=True, default=0)     # Se 1 pagamento ritenute

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{}'.format(self.MPCODICE)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.MPCODICE)
        super().save(*args, **kwargs)

class PAGAMENTI(models.Model):
    PACODICE = models.CharField(max_length=5,primary_key=True)
    PADESCRI = models.CharField(null=True, blank=True, max_length=50)
    PADESEAS = models.CharField(null=True, blank=True, max_length=50) # descrizione per export verso team system

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{}'.format(self.PACODICE)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.PACODICE)
        super().save(*args, **kwargs)

    def legge_rateizzazione(self):
        """Costruisce la rateizzazione definita per questo pagamento."""
        rateizzazione = Rateizzazione()
        rateizzazione.empty()

        for dettaglio in self.pag_dett_set.all().order_by('PDNUMSCA'):
            rateizzazione.definizione.append(ElementoRateizzazione(
                tipo=dettaglio.PDGIORNO,
                tipo_pagamento=(
                    str(dettaglio.PDTIPPAG)
                    if dettaglio.PDTIPPAG is not None
                    else ''
                ),
                intervallo=dettaglio.PDINTERV or 0,
                percentuale=dettaglio.PDPERCEN or Decimal('0'),
                pagata=dettaglio.PDPAGATA or 'N',
                giorno_del_mese=dettaglio.PD_FISSO or 0,
            ))

        return rateizzazione

    # Alias con il nome della procedura Pascal originale.
    def legge_pagamento(self):
        return self.legge_rateizzazione()

    

class PAG_DETT(models.Model):
    PACODICE = models.ForeignKey(PAGAMENTI,  on_delete=models.CASCADE) # on_update non esiste in Django
    PDNUMSCA = models.IntegerField(default=0)
    # Data Doc.,Fine Mese,Inizio Mese'
    PDGIORNO = models.CharField(null=True, blank=True, max_length=11,   
        #il primo valore è quello registrato a database, il secondo quello mostrato a video  
        choices=[
            ("Data Doc.", "Data Doc."),
            ("Fine Mese", "Fine Mese"),
            ("Inizio Mese", "Inizio Mese"),
        ])
    PDINTERV = models.IntegerField(blank=True, null=True, default=0)
    PDPERCEN = models.DecimalField(null=True, blank=True, decimal_places=4,max_digits=20,default=0)
    # on_update non esiste in Django
    PDTIPPAG = models.ForeignKey(MODPAGAM, blank=True, null=True, on_delete=models.RESTRICT)
    # se a S pagato
    PDPAGATA = models.CharField(null=True, blank=True, default='N', max_length=1)
    # giorno fisso (0 se non c'è)
    PD_FISSO = models.IntegerField(null=True, blank=True,default=0)



    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['PACODICE', 'PDNUMSCA'],
                name='pk_PACODICE_PDNUMSCA'
            )
        ]

# Anagrafica codici IVA
class Codiciva(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    CICODICE = models.CharField(max_length=5,primary_key=True)
    CIDESCRI = models.CharField(null=True, blank=True, max_length=254)
    CIPERIVA = models.DecimalField(null=True, blank=True, decimal_places=2,max_digits=5,default=0)

    CIESENTE = models.CharField(null=True, blank=True, max_length=1, default='N') # flag se esente IVA
    CICODCAS = models.SmallIntegerField(null=True,default=0) # codice iva cassa - non utilizzato
    CICODREP = models.SmallIntegerField(null=True,default=0) # codice reparto - non utilizzato    
    CIREVCHA = models.SmallIntegerField(null=True,default=0) # è un flag se 1 reverse charge
    # natura fatturazione elettronica
    CINATURA =models.CharField(null=True, blank=True, max_length=4, default='',
        choices=[
                (""      ,  ""       ),
                ("N1"    ,  "N1"     ),
                ("N2"    ,  "N2"     ),
                ("N2.1"  ,  "N2.1"   ),
                ("N2.2"  ,  "N2.2"   ),
                ("N3"    ,  "N3"     ),
                ("N3.1"  ,  "N3.1"   ),
                ("N3.2"  ,  "N3.2"   ),
                ("N3.3"  ,  "N3.3"   ),
                ("N3.4"  ,  "N3.4"   ),
                ("N3.5"  ,  "N3.5"   ),
                ("N3.6"  ,  "N3.6"   ),
                ("N4"    ,  "N4"     ),
                ("N5"    ,  "N5"     ),
                ("N6"    ,  "N6"     ),
                ("N6.1"  ,  "N6.1"   ),
                ("N6.2"  ,  "N6.2"   ),
                ("N6.3"  ,  "N6.3"   ),
                ("N6.4"  ,  "N6.4"   ),
                ("N6.5"  ,  "N6.5"   ),
                ("N6.6"  ,  "N6.6"   ),
                ("N6.7"  ,  "N6.7"   ),
                ("N6.8"  ,  "N6.8"   ),
                ("N6.9"  ,  "N6.9"   ),
                ("N7"    ,  "N7"     )
        ])

                                
    CIPERIND = models.DecimalField(null=True, blank=True, decimal_places=2,max_digits=5,default=0)   #% detraibilita non utilizzato
    CISPLPAY = models.SmallIntegerField(null=True,default=0) # è un flag se 1 split payment
    CIFCLCOD = models.SmallIntegerField(null=True) #Codice Esterno (Fatture in Cloud)

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{} {}'.format(self.CICODICE, self.CIDESCRI)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False    

# Anagrafica dei nominativi mutuata da Emporio Open (sotto insieme di campi)
class Nominativi(models.Model):

    #Basic Fields
    NOCODICE = models.CharField( max_length=70,primary_key=True)    
    NORAGSOC = models.CharField(null=True, blank=True, max_length=80)
    NOINDIRI = models.CharField(null=True, blank=True, max_length=254)
    NONUMCIV = models.CharField(null=True, blank=True, max_length=20)
    NO_CITTA = models.CharField(null=True, blank=True, max_length=100)
    NOPROVIN = models.CharField(null=True, blank=True, max_length=2)
    NOINDCAP = models.CharField(null=True, blank=True, max_length=5)
    NOTELEF1 = models.CharField(null=True, blank=True, max_length=15)
    NOTELEF2 = models.CharField(null=True, blank=True, max_length=15)
    NOTELEF3 = models.CharField(null=True, blank=True, max_length=15)
    NO_EMAIL = models.CharField(null=True, blank=True, max_length=120)       
    NOPARIVA = models.CharField(null=True, blank=True, max_length=28)       
    NOCODFIS = models.CharField(null=True, blank=True, max_length=16)    
    NONOTEGE = models.TextField(null=True, blank=True)
    NO_NOME = models.CharField(null=True, blank=True, max_length=20)
    NOCOGNOM = models.CharField(null=True, blank=True, max_length=50)
    
    #Utility fields
    slug = models.SlugField()
    NSCARDAT = models.DateTimeField(blank=True, null=True)
    NSMODDAT = models.DateTimeField(blank=True, null=True)
    NONAZION = models.CharField(null=True, blank=True, max_length=2)
    NONOMPEC = models.CharField(null=True, blank=True, max_length=120)
    NOCODSDI = models.CharField(null=True, blank=True, max_length=7)
    # tipo di nominativo (C=Cliente, F=Fornitore)
    NOCODNOM = models.CharField(max_length=5,default=CCATCLI, 
        #il primo valore è quello registrato a database, il secondo quello mostrato a video  
        choices=[
            (CCATCLI, CCATCLI),
            (CCATFOR, CCATFOR),
        ])

    # solo per fornitori!
    NORITPIM = models.DecimalField(null=True, blank=True, default=0, max_digits=5, decimal_places=2) # Ritenuta d'acconto percentuale applicata all'imponibile
    NORITPER = models.DecimalField(null=True, blank=True, default=0, max_digits=5, decimal_places=2) # Ritenuta d'acconto percentuale applicata all'imposta
    NOCASSA = models.DecimalField(null=True, blank=True, default=0, max_digits=5, decimal_places=2) # Cassa previdenziale
    # codice iva da applicare a tutti gli articoli se disponibile
    NOCODIVA = models.ForeignKey(Codiciva, null=True, blank=True,on_delete=models.RESTRICT) # on_update non esiste in Django - OBBLIGATORIA
 
 
    # ruolo per abilitare la modifica degli articoli!
    class Meta:
        ordering = ['NORAGSOC'] 
        permissions = (("Manager_CLienti", "Manager Clienti"),)  


    def __str__(self):
        return '{} {} {}'.format(self.NORAGSOC or '', self.NOTELEF1 or '', self.NO_CITTA or '')


    def get_absolute_url(self):
        return reverse('client-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.NSMODDAT is None:
            self.NSMODDAT = timezone.localtime(timezone.now())
            
        if self.NORAGSOC in (None, ''):
            self.NORAGSOC ='{} {}'.format(self.NOCOGNOM or '', self.NO_NOME or '')

        # se non ho il codice uso la descrizione seguita da un id che disambigua!
        if self.NOCODICE in (None, ''):
            self.NOCODICE = '{}_{}'.format(self.NORAGSOC, str(uuid4()).split('-')[4])

        self.slug = slugify('{}'.format(self.NOCODICE))
        self.NSMODDAT = timezone.localtime(timezone.now())
        
        super(Nominativi, self).save(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False    

    # NON UTILIZZARE nominativi direttamente ma sempre filtre
    @classmethod
    def getClienti(cls):
        return cls.objects.filter(NOCODNOM=CCATCLI)       

    @classmethod
    def getFornitori(cls):
        return cls.objects.filter(NOCODNOM=CCATFOR) 

    @classmethod
    def getNominativi(cls,tipo):
        if tipo==CCATCLI:
            return cls.getClienti()
        elif tipo==CCATFOR:
            return cls.getFornitori()
        else:
            return cls.objects.none()  # Return an empty queryset if tipo is None or unrecognized


# gruppo merceologico
class Grmemast(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    GRCODICE = models.CharField(max_length=10,primary_key=True)
    GRDESCRI = models.CharField(null=True, blank=True, max_length=50)
    # Gruppo da mostrare nel caricamento rapido documenti
    GRCARRAP = models.SmallIntegerField(null=True,default=1) # è un flag se 1 unità non a quantita (es forfettario!)
    
    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{}'.format(self.GRCODICE)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False      
    

# dettaglio gruppo merceologico (la chiave sarebbe la coppia di gruppi mercelogici
# django non gestisce chiavi doppie per cui la chiave è il sotto gruppo.
# ASSUMIAMO CHE UN GRUPPO MERCEOLOGICO NON PUO AVERE PIU' PADRI!
class Grmedett(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    GRSUBGRP = models.CharField(max_length=10,primary_key=True)
    GRCODICE = models.CharField(null=True, blank=True, max_length=10)

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{} {}'.format(self.GRCODICE, self.GRSUBGRP)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False        


# Categoria Articolo
class Categori(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    CACODICE = models.CharField(max_length=5,primary_key=True)
    CADESCRI = models.CharField(null=True, blank=True, max_length=20)

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{} {}'.format(self.CACODICE,self.CADESCRI)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False        

# unita di misura
class Unita(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    UNCODICE = models.CharField(max_length=5,primary_key=True)
    UNDESCRI = models.CharField(null=True, blank=True, max_length=20)
    UN_NOQTA = models.SmallIntegerField(null=True,default=0) # è un flag se 1 unità non a quantita (es forfettario!)
    UNCODFEL = models.CharField(max_length=5, null=True, blank=True)

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{} {}'.format(self.UNCODICE, self.UNDESCRI)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False  
 
    
# Marchi articoli
class Marchiar(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    MACODICE = models.CharField(max_length=20,primary_key=True)
    MADESCRI = models.CharField(null=True, blank=True, max_length=50)
    MACODPRO = models.ForeignKey(Nominativi, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{}'.format(self.MACODICE)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False      


# Anagrafica Articoli mutuata da Emporio Open
class Articoli(models.Model):    
    ARCODICE = models.CharField(max_length=23,primary_key=True)
    ARDESCRI = models.CharField(null=True, blank=True, max_length=80)
    ARDESSUP = models.TextField(null=True, blank=True)
    ARCODIVA = models.ForeignKey(Codiciva, on_delete=models.RESTRICT) # on_update non esiste in Django - OBBLIGATORIA
    ARCODGRU = models.ForeignKey(Grmemast, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django        
    ARPREZZO = models.DecimalField(null=True, blank=True, decimal_places=5,max_digits=20,default=0)
    AR_COSTO = models.DecimalField(null=True, blank=True, decimal_places=5,max_digits=20,default=0)
    ARCODCAT = models.ForeignKey(Categori, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django      
    # per il sotto gruppo a livello di interfaccia va filtrato in base al gruppo selezionato!      
    ARCODSGR = models.ForeignKey(Grmedett, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django            
    ARCODUNI = models.ForeignKey(Unita, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    ARCODMAR = models.ForeignKey(Marchiar, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    ARBARCOD = models.CharField(null=True, blank=True, max_length=40)
    ARBARCO2 = models.CharField(null=True, blank=True, max_length=40)
    ARBARCO3 = models.CharField(null=True, blank=True, max_length=40)
    ARLOTMIN = models.DecimalField(null=True, blank=True, decimal_places=4,max_digits=12,default=0)


    #Utility fields, slug non obbligatorio ma utile per la gestione dei dettagli articolo
    slug = models.SlugField(blank=True, null=True)
    NSCARDAT = models.DateTimeField(blank=True, null=True)
    NSMODDAT = models.DateTimeField(blank=True, null=True)

    # ruolo per abilitare la modifica degli articoli!
    class Meta:
        ordering = ['ARCODICE'] 
        permissions = (("Manager_Articoli", "Manager Articoli"),) 

    def getimage(self):
        tst =Art_link.objects.filter(ALCODART=self.ARCODICE).filter(ALDESCRI='Asset_Resolution_M')
        if not tst:
            return None
        else:
            return tst[0].ARURLLNK  
            
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False

    def __str__(self):
        return '{} {}'.format(self.ARCODICE, self.ARDESCRI)

    def get_absolute_url(self):
        return reverse('articoli-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.NSMODDAT is None:
            self.NSMODDAT = timezone.localtime(timezone.now())
        # se non ho il codice uso la descrizione seguita da un id che disambigua!
        if self.ARCODICE is None:
            self.ARCODICE = '{}_{}'.format(self.ARDESCRI, str(uuid4()).split('-')[4])

        if not self.slug:
            self.slug = slugify(self.ARCODICE)
        self.NSMODDAT = timezone.localtime(timezone.now())

        super(Articoli, self).save(*args, **kwargs)

# lista delle illustrazioni (url) dell'articolo
class Art_link(models.Model):    
    ALCODART = models.ForeignKey(Articoli, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django    
    ARURLLNK = models.CharField(null=True, blank=True, max_length=254)
    ALDESCRI = models.CharField(null=True, blank=True, max_length=50)    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False


@receiver(post_save, sender=Articoli)
def articoli_post_save(sender, instance, created, **kwargs):
    if created:
        instance.nuovo = True
    return instance

@receiver(post_save, sender=Codiciva)
def articoli_post_save(sender, instance, created, **kwargs):
    if created:
        instance.nuovo = True
    return instance

# tabella temporanea per le selezione degli articoli da inserire nel documento..
class tempdettagliodoc(models.Model):
    ARCODICE = models.CharField(max_length=23,primary_key=True)
    ARDESCRI = models.CharField(null=True, blank=True, max_length=80)
    ARDESSUP = models.TextField(null=True, blank=True)    
    ARPREZZO = models.DecimalField(null=True, blank=True, decimal_places=5,max_digits=20,default=0)    
    DOQTAUM1 = models.DecimalField(null=True, blank=True, decimal_places=4,max_digits=12,default=0)
    class Meta:
        managed = False        

# causali di magazzino
class Causmaga (models.Model):
    # segno del magazzino (invariato, aumenta o diminusce la quantità)
    class segno(models.IntegerChoices):
        NO = 0
        AUMENTA = 1
        DIMINUISCE = -1
    
    CMCODICE = models.CharField(max_length=5,primary_key=True)
    CMDESCRI = models.CharField(null=True, blank=True, max_length=50)
    CMCODCOL = models.ForeignKey("self", blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    CMCARSCA = models.IntegerField(choices=segno.choices, default=0)
    CMIMPEGN = models.IntegerField(choices=segno.choices, default=0)
    CMORDIN = models.IntegerField(choices=segno.choices, default=0)
    CMRISERV = models.IntegerField(choices=segno.choices, default=0)

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{} {}'.format(self.CMCODICE, self.CMDESCRI)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False    
    
CICLO = [
    ("V", "Attivo"),
    ("A", "Passivo"),
]


# anagrafica documenti base
class Doctipba(models.Model):
    DTCODICE = models.CharField(max_length=2,primary_key=True)
    DTDESCRI = models.CharField(null=True, blank=True, max_length=50)
    DT_CICLO = models.CharField(null=True, blank=True, max_length=1, choices=CICLO, default='V')
    DTTITOLO = models.CharField(null=True, blank=True, max_length=50) # non utilizzato
    DTORDINE = models.IntegerField(null=True, blank=True)
    DTREGIVA = models.IntegerField(null=True, blank=True, default=0)
    DTPORTAB = models.IntegerField(null=True, blank=True, default=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False   

# Causali documenti: Ordine, Carico, Scarico
class Causdocu(models.Model):
    CDCODICE = models.CharField(max_length=5,primary_key=True)
    CDDESCRI = models.CharField(null=True, blank=True, max_length=50)
    CD_CICLO = models.CharField(null=True, blank=True, max_length=1, choices=CICLO, default='V')
    CDTIPDOC = models.CharField(null=True, blank=True, max_length=2, default='OV')
    CDCAUMAG = models.ForeignKey(Causmaga, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    CDNUMAUT= models.SmallIntegerField(null=True, blank=True, default=0) # se 1 numerazione automatica  
    # campi non gestiti - aggiunti per agevolare l'import da Emporio Open
    CDQUALIT = models.SmallIntegerField(); # int UN 
    # fine blocco campi non gestiti
    CDTIPINT = models.CharField(null=True, blank=True, max_length=3,   
        #il primo valore è quello registrato a database, il secondo quello mostrato a video  
        choices=[
            (CCATCLI,"Cliente" ),
            (CCATFOR,"Fornitore" ),
            (None,"No" ),
        ])

    # campi non gestiti - aggiunti per agevolare l'import da Emporio Open
    CDACCONT   = models.SmallIntegerField(null=True)              # int UN
    CD_STAMPA  = models.SmallIntegerField(null=True)              # int UN
    CDINTDDT   = models.TextField(null=True)                 # mediumtext
    CDPIEDDT   = models.TextField(null=True)                 # mediumtext
    CDPIEDDD   = models.TextField(null=True)                 # mediumtext
    CDPREFER   = models.SmallIntegerField(null=True)
    CDFATDIF   = models.SmallIntegerField(null=True)
    CDSCADEN   = models.SmallIntegerField(null=True)              # int UN
    CDREPFIL   = models.CharField(null=True,max_length=254)
    CDTIPFEL   = models.CharField(null=True,max_length=4)
    CDLIMMAX   = models.DecimalField(null=True,max_digits=20, decimal_places=5)
    CDTITOLO   = models.CharField(null=True,max_length=50)
    CDACCCTX   = models.SmallIntegerField(null=True)              # int UN
    CDARTACC   = models.CharField(null=True,max_length=23)
    CDCAUACC   = models.CharField(null=True,max_length=5)
    CDCODCFN   = models.CharField(null=True,max_length=15)
    CDRITACC   = models.IntegerField(null=True)              # int UN
    CD_SEGNO   = models.SmallIntegerField(null=True)              # int#    
    # fine blocco campi non gestiti
    
    CDINTOBB = models.SmallIntegerField(null=True, blank=True, default=1) # se 1 intestatario obbligatorio
    # campi non gestiti - aggiunti per agevolare l'import da Emporio Open
    CDCOINTE = models.SmallIntegerField(null=True, blank=True, default=1)
    # fine blocco campi non gestiti
    CDGESIVA = models.SmallIntegerField(null=True, blank=True, default=1) # se 1 gestione IVA 
    CDGESPAG = models.SmallIntegerField(null=True, blank=True, default=1) # se 1 gestione pagamenti
    # campi ad oggi non gestiti - inseriti solo per agevolare la migrazione tra Emporio open e web tramite lo script di init.
    CDCATCON   = models.CharField(null=True,max_length=5)
    CDGIOSCA   = models.IntegerField(null=True)
    CD_SERIE   = models.CharField(null=True,max_length=6)
    CD_SERPR   = models.CharField(null=True,max_length=6)
    CDFLGCOR   = models.CharField(null=True,max_length=1)
    CDGESCOM   = models.IntegerField(null=True)
    CGGENCOM   = models.IntegerField(null=True)
    CDNUMCON   = models.IntegerField(null=True)
    CDMOVCOM   = models.IntegerField(null=True)
    CD_CRC   = models.BigIntegerField(null=True)
    CD_DOC   = models.CharField(null=True,max_length=254)
    CDBISCRC   = models.BigIntegerField(null=True)
    CDBISDOC   = models.CharField(null=True,max_length=254)
    CDCAUCON   = models.CharField(null=True,max_length=5)
    CDPAGDEF   = models.ForeignKey(PAGAMENTI, blank=True, null=True, on_delete=models.RESTRICT) 
    CDBANDEF   = models.CharField(null=True,max_length=15)
    CASQLMAS   = models.TextField(null=True)        # mediumtext → TextField
    CASQLIVA   = models.TextField(null=True)
    CASQLSCA   = models.TextField(null=True)
    CDCODCFD   = models.CharField(null=True,max_length=15)
    CDBTNRIG   = models.SmallIntegerField(null=True)
    CDCRIGRD   = models.SmallIntegerField(null=True)
    CDCATALL   = models.CharField(null=True,max_length=15)
    CDOPTION   = models.SmallIntegerField(null=True)
    CDDESSUP   = models.SmallIntegerField(null=True)
    CDNUMCOP   = models.IntegerField(null=True)
    CDGRIVAR   = models.IntegerField(null=True)
    CDCODCAU   = models.CharField(null=True,max_length=5)
    CDCODPOR   = models.CharField(null=True,max_length=5)
    CDCODSPE   = models.CharField(null=True,max_length=5)
    CDCODASP   = models.CharField(null=True,max_length=5)
    CDCODVET   = models.CharField(null=True,max_length=5)
    CDGENPRO   = models.IntegerField(null=True)
    CD_SEDE   = models.CharField(null=True,max_length=5)
    CDLORIVA   = models.SmallIntegerField(null=True)
    CDGENLOT   = models.IntegerField(null=True)
    CDMULTIC   = models.IntegerField(null=True)
    CDBOLCOR   = models.IntegerField(null=True)
    CDGIOBLO   = models.IntegerField(null=True)
    CDAVVPAG   = models.IntegerField(null=True, blank=True)  # int? → opzionale    
    # fine blocco campi non gestiti

    #Utility fields
    slug = models.SlugField()

    def __str__(self):
        return '{} {}'.format(self.CDCODICE, self.CDDESCRI) 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False          

# relazione tra causali documenti
class causdett(models.Model):
    CTCODICE = models.ForeignKey(Causdocu,on_delete=models.RESTRICT,related_name='padre') # on_update non esiste in Django
    CTCADCOL = models.ForeignKey(Causdocu,on_delete=models.RESTRICT,related_name='figlio') # on_update non esiste in Django
    CT_EVADE = models.SmallIntegerField(null=True, blank=True); # in realta 1(evade) o 0 (non evade)
    # campi ad oggi non gestiti - inseriti solo per agevolare la migrazione tra Emporio open e web tramite lo script di init.
    CTPAGAME = models.SmallIntegerField(null=True, blank=True); # in realta 1(importa dati pagamento) o 0 (non importa)
    CTDATACC = models.SmallIntegerField(null=True, blank=True); # in realta 1(importa dati accompagnatori) o 0 (non importa)
    CTRIGRIF = models.CharField(null=True, blank=True, max_length=20); # valori possibili per la riga riferimento, 'No','Crea','Crea con Rif.Est.','Aggiungi a note'
    CTNOTRIF = models.SmallIntegerField(null=True, blank=True); # in realta 1(import note e riferimento esterno) o 0 (non importa)
    CTARTTIP = models.CharField(null=True, blank=True, max_length=20); # tipi di articoli importati, 'Tutti','Solo a Magazzino','Solo Servizi'
    # fine blocco campi non gestiti

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['CTCODICE', 'CTCADCOL'], name='unique_CTCODICE_CTCADCOL')
        ]


sync_status = [
    (0, "Si"),
    (1, "No"),
]

# Testata documenti
class Ord_Mast(models.Model):
    DOCODICE = models.AutoField(primary_key=True)
    DONUMORD = models.IntegerField(null=True, blank=True, default=0)
    DOALFORD = models.CharField(null=True, blank=True, max_length=6)
    DODATORD = models.DateField(blank=True, null=True)
    DONOTE = models.TextField(null=True, blank=True)
    DOCODCAU = models.ForeignKey(Causdocu, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    DOCODINT = models.ForeignKey(Nominativi, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    # related_name per differenziare nel caso in cui si abbiamo più integrità referenziali
    DOCODUTE = models.ForeignKey(User, on_delete=models.PROTECT, related_name='operatore' )    
    SYNC_UPDATE = models.SmallIntegerField(null=True, blank=True, default=1, choices=sync_status) ; # in realta 1(da sincronizzare) o 0 (sincronizzato)   
    
    DOCODPAG = models.ForeignKey(PAGAMENTI, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django

    DOLORIVA = models.CharField(null=True, blank=True, max_length=1, default='N') # flag se documento con prezzi al lordo IVA

    DORITPIM = models.DecimalField(null=True, blank=True, max_digits=5, decimal_places=2, default=0) # Ritenuta d'acconto percentuale applicata all'imponibile
    DORITPER = models.DecimalField(null=True, blank=True,  max_digits=5, decimal_places=2, default=0) # Ritenuta d'acconto percentuale applicata all'imposta
    DORITACC = models.DecimalField(null=True, blank=True, max_digits=20, decimal_places=2, default=0) # Ritenuta d'acconto calcolata sul totale documento

    DOIMPACC = models.DecimalField(null=True, blank=True, max_digits=20, decimal_places=2, default=0) # Importo Acconto
    DOIMPFIN = models.DecimalField(null=True, blank=True, max_digits=20, decimal_places=2, default=0) # Importo Finanziamento
    DO_CASSA = models.DecimalField(
        db_column='DO_CASSA',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
    )

    DOTIPDOC = models.CharField(null=True, blank=True, max_length=2) # tipo base documento (OR,FA,FV...)

    # codice iva da applicare a tutti gli articoli se disponibile (valorizato con NOCODIVA dell'intestatario se disponibile)
    DOTCOIVA = models.ForeignKey(Codiciva, null=True, blank=True,on_delete=models.RESTRICT) # on_update non esiste in Django - OBBLIGATORIA


    #Utility fields
    slug = models.SlugField()

    def __str__(self):
        return '{}/{} del {} Intestatario {} Operatore: {}'.format(self.DONUMORD, self.DOALFORD, self.DODATORD, self.DOCODINT, self.DOCODUTE )

    class Meta:
        ordering = ['-DODATORD'] 
        permissions = (("Manager_Ordini", "Manager Ordini"),) 

    def save(self, *args, **kwargs):

        # da gestire il caricamento automatico del cliente!                            
        intdaSalvare = False;
        if (
            self.DOTCOIVA_id is None
            and self.DOCODINT_id is not None
            and self.DOCODINT.NOCODIVA_id is not None
        ):
            self.DOTCOIVA_id = self.DOCODINT.NOCODIVA_id
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {
                    'DOTCOIVA',
                }
        # marco il documento come da sincronizzare.
        self.SYNC_UPDATE=1
        super().save(*args, **kwargs)
# """         if intdaSalvare:
#             self.DOCODINT.save()    """

    @property
    def TotaleDocumento(self):
        return Ord_dett.objects.filter(DOCODICE=self.DOCODICE).aggregate(totale=Sum(F('DOPREZZO')*F('DOQTAUM1')))['totale']

    # ritorna castelletoIVA e totaliDocumento e importo ritenute...
    def totale_fattura(self):
        """Calcola il castelletto IVA del documento.

        Il risultato contiene un elemento per ogni codice IVA presente nelle
        righe del documento, con imponibile, imposta e base per la ritenuta.
        """
        riepiloghi = {}
        totaliDocumento =datiRiepilogo.totaliDocumento()

        totDocumento=0
        totaleImposta=0
        totImponibile=0
        TotImponibileEsente=0
        totbolli=0

        ritenuteCalcolate = 0

        dettagli = self.ord_dett_set.select_related(
            'DOCODART__ARCODIVA',
            'DOCODIVA',
        ).all()

        for dettaglio in dettagli:
            if dettaglio.DOCODART is None:
                continue

            codice_iva = (
                dettaglio.DOCODIVA
                or self.DOTCOIVA
                or dettaglio.DOCODART.ARCODIVA
            )
            codice = codice_iva.CICODICE if codice_iva else ''
            aliquota = codice_iva.CIPERIVA if codice_iva else Decimal('0')
            valore_riga = (
                (dettaglio.DOPREZZO or Decimal('0'))
                * (dettaglio.DOQTAUM1 or Decimal('0'))
            )

            if codice not in riepiloghi:
                if len(riepiloghi) >= 6:
                    raise ValueError(
                        'Sono presenti più di 6 percentuali IVA diverse.'
                    )

                riepiloghi[codice] = DatiRiepilogo(
                    codice_iva=codice,
                    percentuale_iva=aliquota,
                    esente=codice_iva.CIESENTE == 'S' if codice_iva else False,
                    rev_charge=codice_iva.CIREVCHA == 1 if codice_iva else False,
                    split_payment=codice_iva.CISPLPAY == 1 if codice_iva else False,
                )

            riepilogo = riepiloghi[codice]
            riepilogo.imponibile += valore_riga
            riepilogo.imponibile_calcolo_ritenuta += valore_riga

        for riepilogo in riepiloghi.values():
            imponibile_originale = riepilogo.imponibile

            if self.DOLORIVA == 'S' and riepilogo.percentuale_iva != 0:
                riepilogo.imponibile = funzioni.scorporo(
                    imponibile_originale,
                    riepilogo.percentuale_iva,
                    2,
                )
            else:
                riepilogo.imponibile = imponibile_originale.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_EVEN
                )

            riepilogo.imponibile_calcolo_ritenuta = (
                riepilogo.imponibile_calcolo_ritenuta.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_EVEN
                )
            )
            if riepilogo.rev_charge:
                riepilogo.imposta = Decimal('0.00')
            elif self.DOLORIVA == 'S':
                riepilogo.imposta = (
                    imponibile_originale - riepilogo.imponibile
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
            else:
                riepilogo.imposta = (
                    riepilogo.imponibile
                    * riepilogo.percentuale_iva
                    / Decimal('100')
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
            totaleImposta=totaleImposta+riepilogo.imposta;
            totImponibile=totImponibile+ riepilogo.imponibile;

            # aggiungo al totale esente l'imposta esente (se voce IVA esente).
            if riepilogo.esente:
                TotImponibileEsente=TotImponibileEsente+riepilogo.imponibile

            # sommo totale imponibile ed imposta (imposta solo se non è splitpayment)
            totDocumento= totDocumento+ riepilogo.imponibile
            if not riepilogo.split_payment:
                totDocumento= totDocumento+ riepilogo.imposta;


        # Calcolo della ritenuta. DOTIPRIG non e' ancora presente in Ord_dett,
        # quindi per ora tutte le righe contribuiscono alla base imponibile.
        base_ritenuta = sum(
            (riepilogo.imponibile_calcolo_ritenuta for riepilogo in riepiloghi.values()),
            Decimal('0'),
        )

        cassa_percentuale = (
            self.DOCODINT.NOCASSA
            if self.DOCODINT is not None
            else Decimal('0')
        ) or Decimal('0')
        if cassa_percentuale > 0:
            cassa = (
                base_ritenuta * cassa_percentuale / Decimal('100')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
            # alla base di calcolo della ritenuta va aggiunta la cassa nel caso di INPS Gestione Separata (Flag INPS su fornitore)
            #base_ritenuta += cassa (iif(bCassaINPS,valoreRigoCassa,0))

        if self.DORITPER is not None and self.DORITPIM is not None and self.DORITPER != 0 and self.DORITPIM != 0:
            base_ritenuta = (
                base_ritenuta * self.DORITPIM / Decimal('100')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
            ritenuteCalcolate = (
                base_ritenuta * self.DORITPER / Decimal('100')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        else:
            ritenuteCalcolate = Decimal('0.00')

        totaliDocumento.totDocumento= totDocumento-ritenuteCalcolate;
        totaliDocumento.totIMposta=totaleImposta;
        totaliDocumento.totImponibileEsente=TotImponibileEsente;
        totaliDocumento.totBolli=totbolli;
        totaliDocumento.totRitenuta=ritenuteCalcolate;


        return list(riepiloghi.values()), totaliDocumento

                
    # booleano true evaso!
    @property
    def DocumentoEvaso(self):
        evaso = Ord_dett.objects.filter(DOCODICE=self.DOCODICE).aggregate(evasi=Sum(F('DOFLEVAS')))['evasi']
        return evaso is not None and evaso>0        

    # chiave del documento che ha evaso
    @property
    def getEvasoDa(self):
        evasoDaTst = Ord_dett.objects.filter(DOCODRIF__DOCODICE=self.DOCODICE).values('DOCODICE')
        if evasoDaTst.exists():
            return evasoDaTst[0]['DOCODICE']
        else:
            return None


    @property
    def articoliDocumento(self):
        # groupConcat = Ord_dett.objects.filter(DOCODICE=self.DOCODICE).values('DOCODICE').annotate(value=GroupConcat("DOCODART",True)).annotate(somma=Sum("DOQTAUM1", default=0))
        # if groupConcat.exists():
        #     return '{} - {}'.format(int(groupConcat[0]['somma']) , groupConcat[0]['value'])
        # else:
        return "" 
    
class GroupConcat(Aggregate):
    function = 'GROUP_CONCAT'
    template = '%(function)s(%(distinct)s%(expressions)s%(ordering)s%(separator)s)'
    allow_distinct = True

    def __init__(self, expression, distinct=False, ordering=None, separator=',', **extra):
        super().__init__(
            expression,
            distinct='DISTINCT ' if distinct else '',
            ordering=' ORDER BY %s' % ordering if ordering is not None else '',
            separator=' SEPARATOR "%s"' % separator,
            output_field=CharField(),
            **extra
        )  

# scadenze documento
class Scadenze(models.Model):
    SCCODICE = models.ForeignKey(Ord_Mast, blank=True, null=True, on_delete=models.CASCADE) # on_update non esiste in Django
    SCNUMSCA = models.IntegerField(null=True, blank=True, default=0)
    SCDATSCA = models.DateField(blank=True, null=True)
    SCIMPSCA = models.DecimalField(null=True, blank=True, decimal_places=5,max_digits=20,default=0)
    # se a S pagato
    SCPAGATA = models.CharField(null=True, blank=True, default='N', max_length=1)
    # on_update non esiste in Django
    SCTIPPAG = models.ForeignKey(MODPAGAM, blank=True, null=True, on_delete=models.RESTRICT) 

    SCDATPAG = models.DateField(blank=True, null=True)
    # sarebbe SC__NOTE ma django non accetta l'underscore
    SCNOTE = models.TextField(null=True, blank=True)    

class Rivadett(models.Model):
    """Dettaglio degli importi per codice IVA.

    La tabella esistente ha una chiave composta (RICODICE, RICODIVA),
    non supportata nativamente da Django 4.2.
    """
    RICODICE = models.ForeignKey(Ord_Mast,  on_delete=models.CASCADE)
    RICODIVA = models.ForeignKey(Codiciva,  on_delete=models.RESTRICT) # on_update non esiste in Django
    RIIMPONI = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True
    )
    RIIMPOST = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True
    )

# dettaglio documenti (la chiave multipla non è gestita in Django per cui ha l'id a database)
# a codice si utilizza DOCODICE
class Ord_dett(models.Model):
    DOCODICE = models.ForeignKey(Ord_Mast, blank=True, null=True, on_delete=models.CASCADE) # on_update non esiste in Django
    DONUMRIG = models.IntegerField(null=True, blank=True, default=0)
    DOCODART = models.ForeignKey(Articoli, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    DOQTAUM1 = models.DecimalField(null=True, blank=True, decimal_places=4,max_digits=12,default=0)
    DODESART = models.CharField(null=True, blank=True, max_length=80)
    DOPREZZO = models.DecimalField(null=True, blank=True, decimal_places=5,max_digits=20,default=0)
    DODESSUP = models.TextField(null=True, blank=True)    
    DOCODIVA = models.ForeignKey(
        Codiciva,
        blank=True,
        null=True,
        on_delete=models.RESTRICT,
    )

    # evasione riferimento riga documento (rispetto a Emporio open qui abbiamo direttamente l'id di riga)
    # Non si può cancellare una riga evasa 
    DOCODRIF = models.ForeignKey("Ord_dett", blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    # se a 1 evaso 
    DOFLEVAS = models.IntegerField(null=True, blank=True, default=0)
    # rispetto a Emporio Open non ci occorre il segno.
    # segno movimento di magazzino
    DOCARSCA = models.IntegerField(null=True, blank=True, default=0)
    DORISERV = models.IntegerField(null=True, blank=True, default=0)
    DOIMPEGN = models.IntegerField(null=True, blank=True, default=0)
    DOORDINA = models.IntegerField(null=True, blank=True, default=0)
    DOCODUNI = models.ForeignKey(Unita, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django
    DORIGCASSA = models.BooleanField(default=False)

    # al salvataggio imposto i flag di magazzzino
    def save(self, *args, **kwargs):
        if self.DOCODIVA_id is None and self.DOCODART_id is not None:
            codice_iva_documento = (
                self.DOCODICE.DOTCOIVA_id
                if self.DOCODICE_id is not None
                else None
            )
            self.DOCODIVA_id = codice_iva_documento or Articoli.objects.filter(
                pk=self.DOCODART_id
            ).values_list('ARCODIVA_id', flat=True).first()

        # leggo la causale di magazzino collegata..
        causMaga = self.DOCODICE.DOCODCAU.CDCAUMAG
        carSca=0
        ordina=0
        impegn=0
        riserv=0
        # se ho la causale la leggo!
        if causMaga is not None:
            carSca=causMaga.CMCARSCA
            ordina=causMaga.CMORDIN
            impegn=causMaga.CMIMPEGN
            riserv=causMaga.CMRISERV
            self.DOCARSCA=carSca
            self.DOORDINA=ordina
            # se riga evade un ordine a cliente allora lo scarico decrementa anche l'impegnato
            if self.DOCODRIF!=None and self.DOCODRIF.DOCODICE.DOCODCAU.CDCAUMAG.CMIMPEGN==1:
                impegn=-1
            self.DOIMPEGN=impegn
            self.DORISERV=riserv               

        super().save(*args, **kwargs)


class Azienda(models.Model):
    NOME = models.CharField(max_length=50, primary_key=True, default="")
    EURO = models.BooleanField(null=True, blank=True)
    LOGO = models.BinaryField(null=True, blank=True)
    INDIRIZZO = models.CharField(max_length=50, null=True, blank=True)
    TELEFONO = models.CharField(max_length=30, null=True, blank=True)
    FAX = models.CharField(max_length=30, null=True, blank=True)
    CODICEIVA = models.CharField(max_length=15, null=True, blank=True)
    TASSO = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    NOTE = models.TextField(null=True, blank=True)
    AVVISI = models.TextField(null=True, blank=True)
    CODFEST = models.CharField(max_length=5, null=True, blank=True)
    AZDIRBCK = models.CharField(max_length=250, null=True, blank=True)
    AZDAYBCK = models.CharField(max_length=7, null=True, blank=True)
    AZORABCK = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZMINBCK = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZUSR_ON = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZSTAMPA = models.CharField(max_length=1, null=True, blank=True)
    AZDAYIND = models.CharField(max_length=7, null=True, blank=True)
    AZ_CLOSE = models.CharField(max_length=1, null=True, blank=True)
    AZ_ADMIN = models.CharField(max_length=5, null=True, blank=True)
    AZNUMEXP = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZDATEXP = models.DateField(null=True, blank=True)
    AZORAEXP = models.IntegerField(null=True, blank=True)
    AZMINEXP = models.IntegerField(null=True, blank=True)
    AZPRZDEC = models.IntegerField(null=True, blank=True)
    AZPOSTIT = models.CharField(max_length=1, null=True, blank=True)
    AZCOLPOS = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZ_STATO = models.IntegerField(null=True, blank=True)
    AZCOLHLP = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZCOLALL = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    AZPOSDAT = models.CharField(max_length=1, null=True, blank=True)
    AZDECMAG = models.IntegerField(null=True, blank=True)
    AZDOCUNI = models.CharField(max_length=50, null=True, blank=True)
    AZKEYCAS = models.CharField(max_length=1, null=True, blank=True)
    AZDEBSYS = models.CharField(max_length=1, null=True, blank=True)
    AZBAFONT = models.CharField(max_length=50, default="MS Sans Serif", null=True, blank=True)
    AZBAFSIZ = models.IntegerField(default=8, null=True, blank=True)
    AZ_EMAIL = models.CharField(max_length=254, null=True, blank=True)
    AZBKMAIL = models.CharField(max_length=254, null=True, blank=True)
    AZDAYEML = models.CharField(max_length=7, null=True, blank=True)
    AZ_SMTP = models.CharField(max_length=50, null=True, blank=True, db_column="AZ__SMTP")
    AZ_PORT = models.IntegerField(null=True, blank=True, db_column="AZ__PORT")
    AZ_USER = models.CharField(max_length=50, null=True, blank=True, db_column="AZ__USER")
    AZ_PWD = models.CharField(max_length=50, null=True, blank=True, db_column="AZ___PWD")
    AZCIIOFF = models.IntegerField(null=True, blank=True)
    AZDIRATT = models.CharField(max_length=254, null=True, blank=True)
    AZ_SSL = models.CharField(max_length=1, default="N", null=True, blank=True, db_column="AZ___SSL")
    AZ_WEB = models.CharField(max_length=254, null=True, blank=True, db_column="AZ___WEB")
    AZOFFSET = models.IntegerField(default=20, null=True, blank=True)
    AZPRSTEP = models.IntegerField(default=0, null=True, blank=True)
    AZGESSYN = models.IntegerField(default=0, null=True, blank=True)
    AZSYNINP = models.CharField(max_length=5, null=True, blank=True)
    AZSYNOUT = models.CharField(max_length=5, null=True, blank=True)
    AZEMAILSY = models.CharField(max_length=255, null=True, blank=True)
    AZMAILPW = models.CharField(max_length=50, null=True, blank=True)
    AZCODMSR = models.CharField(max_length=10, default="DEFAULT", null=True, blank=True)
    AZNUMCIV = models.CharField(max_length=10, null=True, blank=True)
    AZ_CITTA = models.CharField(max_length=50, null=True, blank=True)
    AZ_PR = models.CharField(max_length=5, null=True, blank=True, db_column="AZ____PR")
    AZMAXATT = models.IntegerField(default=1, null=True, blank=True)
    AZCODFIS = models.CharField(max_length=16, null=True, blank=True)
    AZSRVSYN = models.CharField(max_length=50, default="imap.gmail.com", null=True, blank=True)
    AZORAAPE = models.IntegerField(null=True, blank=True)
    AZORAPRA = models.IntegerField(null=True, blank=True)
    AZORAPOM = models.IntegerField(null=True, blank=True)
    AZORAFIN = models.TimeField(default=time(17, 0), null=True, blank=True)
    AZMODQUA = models.CharField(max_length=254, null=True, blank=True)
    AZCODGCQ = models.CharField(max_length=5, null=True, blank=True)
    AZMINCLO = models.SmallIntegerField(default=2, null=True, blank=True)
    AZCODIVA = models.CharField(max_length=5, null=True, blank=True)
    AZCODUNI = models.CharField(max_length=5, null=True, blank=True)
    AZCODREP = models.CharField(max_length=5, null=True, blank=True)
    AZCODCAT = models.CharField(max_length=5, null=True, blank=True)
    AZLENCLI = models.IntegerField(default=5, null=True, blank=True)
    AZLENART = models.IntegerField(default=13, null=True, blank=True)
    AZCODBAR = models.IntegerField(null=True, blank=True)
    AZMAGDEF = models.CharField(max_length=5, default="00001", null=True, blank=True)
    AZMULMAG = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZVARART = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZSERCLI = models.CharField(max_length=23, null=True, blank=True)
    AZSERPRO = models.CharField(max_length=23, null=True, blank=True)
    AZCODVAL = models.CharField(max_length=3, null=True, blank=True)
    AZARTDES = models.CharField(max_length=1, null=True, blank=True)
    AZPRGINT = models.IntegerField(null=True, blank=True)
    AZMAGWIP = models.CharField(max_length=5, null=True, blank=True)
    AZPAGDEF = models.CharField(max_length=5, null=True, blank=True)
    AZARTINS = models.ForeignKey(
        Articoli,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="aziende_articolo_iscrizione",
        verbose_name="Articolo iscrizione",
    )
    AZARTTES = models.ForeignKey(
        Articoli,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="aziende_articolo_tessera",
        verbose_name="Articolo tessera",
    )
    AZBANDEF = models.CharField(max_length=15, null=True, blank=True)
    AZMODCAS = models.CharField(max_length=1, null=True, blank=True)
    AZINTDDT = models.TextField(null=True, blank=True)
    AZPIEDDT = models.TextField(null=True, blank=True)
    AZPIEDDD = models.TextField(null=True, blank=True)
    AZSTPRIG = models.IntegerField(default=0, null=True, blank=True)
    AZGRUPRZ = models.CharField(max_length=5, null=True, blank=True)
    AZMODMAT = models.CharField(max_length=1, default="S", null=True, blank=True)
    AZSTAGRU = models.IntegerField(default=0, null=True, blank=True)
    AZMODUBI = models.CharField(max_length=1, default="S", null=True, blank=True)
    AZMODPRO = models.CharField(max_length=1, default="S", null=True, blank=True)
    AZMODCLA = models.CharField(max_length=1, default="S", null=True, blank=True)
    AZGESSEM = models.IntegerField(default=0, null=True, blank=True)
    AZPROVVI = models.IntegerField(null=True, blank=True)
    AZCODTEL = models.CharField(max_length=23, null=True, blank=True)
    AZMODRIP = models.CharField(max_length=1, null=True, blank=True)
    AZINTBAN = models.CharField(max_length=70, null=True, blank=True)
    AZINTBAR = models.CharField(max_length=70, null=True, blank=True)
    AZCODMAR = models.CharField(max_length=5, null=True, blank=True)
    AZMOD_QU = models.CharField(max_length=1, default="S", null=True, blank=True)
    AZALFPRE = models.CharField(max_length=2, default="A", null=True, blank=True)
    AZSCACHK = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZLORIVA = models.SmallIntegerField(default=0, null=True, blank=True)
    AZDOCPRI = models.CharField(max_length=50, null=True, blank=True)
    AZMODCAL = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZREGFIS = models.CharField(max_length=4, default="RF01", null=True, blank=True)
    AZINDCAP = models.CharField(max_length=5, null=True, blank=True)
    AZMARDOC = models.SmallIntegerField(default=0, null=True, blank=True)
    AZINTINT = models.CharField(max_length=70, null=True, blank=True)
    AZCODCAS = models.ForeignKey(
        Articoli,
        db_column='AZCODCAS',
        to_field='ARCODICE',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name='aziende_articolo_cassa',
        verbose_name='Articolo cassa previdenziale',
    )
    AZCATCNO = models.CharField(max_length=5, default="CLFOR", null=True, blank=True)
    AZCATCAR = models.CharField(max_length=5, default="ART", null=True, blank=True)
    AZCOMRIT = models.CharField(max_length=15, null=True, blank=True)
    AZCOMPRE = models.CharField(max_length=15, null=True, blank=True)
    AZCOMCAS = models.CharField(max_length=15, null=True, blank=True)
    AZCOMSPE = models.CharField(max_length=15, null=True, blank=True)
    AZCOMCLI = models.CharField(max_length=15, null=True, blank=True)
    AZCOMFOR = models.CharField(max_length=15, null=True, blank=True)
    AZCOMIVA = models.CharField(max_length=15, null=True, blank=True)
    AZCOMIVV = models.CharField(max_length=15, null=True, blank=True)
    AZIMPBOL = models.DecimalField(max_digits=20, decimal_places=5, default=Decimal("2.00000"), null=True, blank=True)
    AZMINBOL = models.DecimalField(max_digits=20, decimal_places=5, default=Decimal("77.47000"), null=True, blank=True)
    AZCODBOL = models.CharField(max_length=5, default="ESC15", null=True, blank=True)
    AZLISVEN = models.CharField(max_length=15, null=True, blank=True)
    AZCAUFCO = models.CharField(max_length=5, default="FVCO", null=True, blank=True)
    AZGESCOM = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZGESORG = models.CharField(max_length=1, default="N", null=True, blank=True)
    AzTipInt = models.CharField(max_length=5, null=True, blank=True)
    Az_Font = models.CharField(max_length=50, null=True, blank=True, db_column="Az__Font")
    AZSZFONT = models.FloatField(null=True, blank=True)
    AzIdonei = models.CharField(max_length=5, null=True, blank=True)
    AZGARMES = models.IntegerField(default=24, null=True, blank=True)
    AZDATCON = models.IntegerField(default=0, null=True, blank=True)
    AZPIALAY = models.IntegerField(default=0, null=True, blank=True)
    AZSTXINT = models.SmallIntegerField(default=0, null=True, blank=True)
    AZSTSMTP = models.SmallIntegerField(default=0, null=True, blank=True)
    AZCODMST = models.CharField(max_length=10, default="DEFAULT", null=True, blank=True)
    AZCODMCL = models.CharField(max_length=50, null=True, blank=True)
    AZMAILTC = models.IntegerField(default=1, null=True, blank=True)
    AZAUTOCC = models.IntegerField(default=0, null=True, blank=True)
    AZGRUTEC = models.CharField(max_length=5, null=True, blank=True)
    AZPCOPOS = models.FloatField(default=255, null=True, blank=True)
    AZDFLPRI = models.FloatField(null=True, blank=True)
    azcodpri = models.FloatField(null=True, blank=True)
    AZ_CCIA = models.CharField(max_length=50, null=True, blank=True, db_column="AZ__CCIA")
    AZITELID = models.CharField(max_length=50, null=True, blank=True)
    AZDATLIB = models.DateField(default=date(2014, 10, 15), null=True, blank=True)
    AZPDFFRO = models.IntegerField(default=0, null=True, blank=True)
    AZCATBOL = models.CharField(max_length=10, null=True, blank=True)
    AZDURDOC = models.SmallIntegerField(default=0, null=True, blank=True)
    AZSOSPSO = models.CharField(max_length=5, null=True, blank=True)
    AZCAUINT = models.CharField(max_length=5, null=True, blank=True)
    AZSRFACO = models.CharField(max_length=23, null=True, blank=True)
    AZCAUCOM = models.CharField(max_length=5, null=True, blank=True)
    AZGESCON = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZCAUINC = models.CharField(max_length=5, null=True, blank=True)
    AZCAUPAG = models.CharField(max_length=5, null=True, blank=True)
    AZ_GUEST = models.CharField(max_length=5, null=True, blank=True)
    AZMSEVPE = models.CharField(max_length=10, null=True, blank=True)
    AZMSEVCL = models.CharField(max_length=10, null=True, blank=True)
    AZBCTIP1 = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    AZBCLAB1 = models.CharField(max_length=50, default="Barcode EAN", null=True, blank=True)
    AZBCTIP2 = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    AZBCLAB2 = models.CharField(max_length=50, default="Barcode 2", null=True, blank=True)
    AZBCTIP3 = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    AZBCLAB3 = models.CharField(max_length=50, default="Barcode 3", null=True, blank=True)
    AZBCPXB1 = models.CharField(max_length=12, default="99", null=True, blank=True)
    AZBCPXB2 = models.CharField(max_length=12, null=True, blank=True)
    AZBCPXB3 = models.CharField(max_length=12, null=True, blank=True)
    AZMODING = models.CharField(max_length=1, null=True, blank=True)
    AZCANTIE = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZPRAINI = models.TimeField(default=time(12, 0), null=True, blank=True)
    AZPRAFIN = models.TimeField(default=time(13, 0), null=True, blank=True)
    AZORAINI = models.TimeField(default=time(8, 0), null=True, blank=True)
    AZAPIUID = models.CharField(max_length=60, null=True, blank=True)
    AZAPIKEY = models.CharField(max_length=60, null=True, blank=True)
    AZAPIURL = models.CharField(max_length=254, null=True, blank=True)
    AZBCSTA1 = models.PositiveIntegerField(default=0, null=True, blank=True)
    AZBCSTA2 = models.PositiveIntegerField(default=0, null=True, blank=True)
    AZBCSTA3 = models.PositiveIntegerField(default=0, null=True, blank=True)
    AZUTECAN = models.CharField(max_length=5, null=True, blank=True)
    AZGRUCAN = models.CharField(max_length=5, null=True, blank=True)
    AZCODSDI = models.CharField(max_length=7, null=True, blank=True)
    AZWEBURL = models.CharField(max_length=254, null=True, blank=True)
    AZWEBART = models.IntegerField(default=0, null=True, blank=True)
    AZWEBCLI = models.IntegerField(default=0, null=True, blank=True)
    AZUTECAP = models.CharField(max_length=5, null=True, blank=True)
    AZCATEVI = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    AZCATEVP = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    AZCATEVF = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    AZBCTIV1 = models.PositiveSmallIntegerField(default=0, null=True, blank=True)
    AZBCLAV1 = models.CharField(max_length=50, default="Barcode EAN", null=True, blank=True)
    AZBCPXV1 = models.CharField(max_length=12, null=True, blank=True)
    AZBCSTV1 = models.PositiveIntegerField(default=0, null=True, blank=True)
    AZUTEALE = models.CharField(max_length=5, null=True, blank=True, db_index=True)
    AZGIOALE = models.IntegerField(default=0, null=True, blank=True)
    AZMODLOT = models.CharField(max_length=1, default="N", null=True, blank=True)
    AZCONLOT = models.CharField(max_length=50, null=True, blank=True)
    AZCONPAR = models.CharField(max_length=100, null=True, blank=True)
    AZLAVDEF = models.CharField(max_length=20, null=True, blank=True)
    AZDUEUNI = models.IntegerField(default=0, null=True, blank=True)
    AZ_CASSA = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    AZSERBOL = models.CharField(max_length=23, null=True, blank=True)
    AZNOTBOL = models.CharField(max_length=254, null=True, blank=True)
    AZMENPRV = models.IntegerField(default=0, null=True, blank=True)
    AZTIPAFE = models.CharField(max_length=35, default="CODICE ARTICOLO", null=True, blank=True)

    class Meta:
        db_table = "azienda"
        indexes = [
            models.Index(fields=["AZCONLOT", "AZCONPAR"], name="azienda_conlot_conpar_idx"),
        ]

    @classmethod
    def get_azienda(cls):
        key = "documenti_azienda"
        azienda = cache.get(key)
        if azienda is None:
            azienda = cls.objects.order_by("NOME").first()
            if azienda is None:
                raise cls.DoesNotExist(
                    "La tabella azienda non contiene record. Eseguire le migrazioni."
                )
            cache.set(key, azienda, timeout=None)
        return azienda

    def _invalidate_cache_after_commit(self):
        transaction.on_commit(lambda: cache.delete("documenti_azienda"))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._invalidate_cache_after_commit()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        self._invalidate_cache_after_commit()
        return result

    def __str__(self):
        return self.NOME


# da trasformare in Azienda da Emporio Open
class Settings(models.Model):
    # per avere un solo record...
    singleton = models.BooleanField(default=True, primary_key=True, editable=False)

    #Basic Fields
    clientName = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    addressLine1 = models.CharField(null=True, blank=True, max_length=200)
    province = models.CharField(null=True, blank=True, max_length=2)#choices=PROVINCES,
    postalCode = models.CharField(null=True, blank=True, max_length=10)
    phoneNumber = models.CharField(null=True, blank=True, max_length=100)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    taxNumber = models.CharField(null=True, blank=True, max_length=20)

    # gestione documenti
    AZPAGDEF = models.ForeignKey(PAGAMENTI, blank=True, null=True, on_delete=models.RESTRICT) # on_update non esiste in Django


    #Utility fields
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField()
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    # carico in cache i settings...
    @classmethod
    def get_settings(cls):
        key = "app_settings"
        settings = cache.get(key)
        if settings is None:
            settings, created = cls.objects.get_or_create(pk=True)
            cache.set(key, settings, timeout=60 * 60)  # la cache dura un'ora
        return settings

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(singleton=True),
                name='impostazioni_singleton'
            )
        ]


    def __str__(self):
        return '{} {} {}'.format(self.clientName, self.province, self.uniqueId)


    def get_absolute_url(self):
        return reverse('settings-detail', kwargs={'slug': self.slug})


    def save(self, *args, **kwargs):
        # un solo record con singleton a true
        self.singleton = True
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {} {}'.format(self.clientName, self.province, self.uniqueId))

        self.slug = slugify('{} {} {}'.format(self.clientName, self.province, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())

        super(Settings, self).save(*args, **kwargs)
        # forzo di ricaricare la cache al salvataggio delle impostazioni
        cache.delete("app_settings")

# menù a database
class MenuItem(models.Model):
    label = models.CharField(max_length=100)
    url_name = models.CharField(max_length=100, blank=True, null=True)
    tipoDocumento = models.CharField(max_length=1, blank=True, null=True,   
        #il primo valore è quello registrato a database, il secondo quello mostrato a video  
        choices=[
            ("A","Ciclo Acquisti" ),
            ("V","Ciclo Vendite" ),
            ("I","Documenti Interni" ),
        ])
    icon = models.CharField(max_length=100, blank=True)  # es: "fa-solid fa-box"
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE
    )
    ordine = models.IntegerField(default=0)
    visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordine"]

    def __str__(self):
        return self.label

# elenco comuni per faciltare il caricamento delle anagrafiche con gli indirizzi...
class Comuni(models.Model):
    COCODICE = models.CharField(max_length=6, primary_key=True)
    CODESCRI = models.CharField(max_length=80, null=True, blank=True)
    CO_PR = models.CharField(max_length=2, null=True, blank=True)
    COPROGRE = models.CharField(max_length=3, null=True, blank=True)

    def __str__(self):
        return f"{self.COCODICE} - {self.CODESCRI}"
