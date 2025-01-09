from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from uuid import uuid4
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum, Count,Max,Min, F,Aggregate, CharField,OuterRef
from django.db.models.signals import post_save
from django.dispatch import receiver
import io
import xml.etree.ElementTree as ET
from xml.etree import ElementTree

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

# Anagrafica codici IVA
class Codiciva(models.Model):
    # sui codici iva va bene usare codice IVA come chiave.
    CICODICE = models.CharField(max_length=5,primary_key=True)
    CIDESCRI = models.CharField(null=True, blank=True, max_length=254)
    CIPERIVA = models.DecimalField(null=True, blank=True, decimal_places=2,max_digits=5,default=0)

    #Utility fields
    slug = models.SlugField()    

    def __str__(self):
        return '{} {}'.format(self.CICODICE, self.CIDESCRI)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # per gestire in fase di caricamento da Emporio Open se record inserito o modificao
        self.nuovo = False    

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


    #Utility fields
    slug = models.SlugField()
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
            self.slug = slugify('{} {}'.format(self.ARDESCRI, self.ARDESSUP))

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
        # marco il documento come da sincronizzare.
        self.SYNC_UPDATE=1
        super().save(*args, **kwargs)
# """         if intdaSalvare:
#             self.DOCODINT.save()    """

    @property
    def TotaleDocumento(self):
        total = Ord_dett.objects.filter(DOCODICE=self.DOCODICE).aggregate(totale=Sum(F('DOPREZZO')*F('DOQTAUM1')))['totale']
        return total
                
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
        groupConcat = Ord_dett.objects.filter(DOCODICE=self.DOCODICE).values('DOCODICE').annotate(value=GroupConcat("DOCODART",True)).annotate(somma=Sum("DOQTAUM1"))
        if groupConcat.exists():
            return '{} - {}'.format(int(groupConcat[0]['somma']) , groupConcat[0]['value'])
        else:
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

    # al salvataggio imposto i flag di magazzzino
    def save(self, *args, **kwargs):
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


# da trasformare in Azienda da Emporio Open
class Settings(models.Model):

    #Basic Fields
    clientName = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    addressLine1 = models.CharField(null=True, blank=True, max_length=200)
    province = models.CharField(null=True, blank=True, max_length=2)#choices=PROVINCES,
    postalCode = models.CharField(null=True, blank=True, max_length=10)
    phoneNumber = models.CharField(null=True, blank=True, max_length=100)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    taxNumber = models.CharField(null=True, blank=True, max_length=20)


    #Utility fields
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField()
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)


    def __str__(self):
        return '{} {} {}'.format(self.clientName, self.province, self.uniqueId)


    def get_absolute_url(self):
        return reverse('settings-detail', kwargs={'slug': self.slug})


    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {} {}'.format(self.clientName, self.province, self.uniqueId))

        self.slug = slugify('{} {} {}'.format(self.clientName, self.province, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())

        super(Settings, self).save(*args, **kwargs)

