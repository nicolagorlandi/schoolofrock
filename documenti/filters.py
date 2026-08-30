import django_filters 
from django.db.models import Q,Case, When, F, DateTimeField,Subquery,FloatField,Sum
from datetime import timedelta
from django.utils.timezone import now
from django_filters import ChoiceFilter
from django.utils.translation import gettext as _

from .models import *
from dal import autocomplete
from django import forms


def _K6truncate(dt):
    return dt.date()

# filtro per date (oggi, ieri, ultimi 7 giorni, ultimo mese, ect ect)
class k6DateRangeFilter(ChoiceFilter):
    choices = [
        ('nextWeek', _('Next Week')),
        ('tomorrow', _('Tomorrow')),
        ('today', _('Today')),
        ('yesterday', _('Yesterday')),
        ('week', _('Past 7 days')),
        ('month', _('This month')),
        ('year', _('This year')),
    ]

    filters = {
        'nextWeek': lambda qs, name: qs.filter(**{
            '%s__lte' % name: _K6truncate(now() + timedelta(days=7)),
            '%s__gt' % name: _K6truncate(now() + timedelta(days=1)),
        }),
        'tomorrow': lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month,
            '%s__day' % name: now().day+1
        }),        
        'today': lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month,
            '%s__day' % name: now().day
        }),
        'yesterday': lambda qs, name: qs.filter(**{
            '%s__year' % name: (now() - timedelta(days=1)).year,
            '%s__month' % name: (now() - timedelta(days=1)).month,
            '%s__day' % name: (now() - timedelta(days=1)).day,
        }),
        'week': lambda qs, name: qs.filter(**{
            '%s__gte' % name: _K6truncate(now() - timedelta(days=7)),
            '%s__lt' % name: _K6truncate(now() + timedelta(days=1)),
        }),
        'month': lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month
        }),
        'year': lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
        }),
    }

    def __init__(self, choices=None, filters=None, *args, **kwargs):
        if choices is not None:
            self.choices = choices
        if filters is not None:
            self.filters = filters

        unique = set([x[0] for x in self.choices]) ^ set(self.filters)
        assert not unique, \
            "Keys must be present in both 'choices' and 'filters'. Missing keys: " \
            "'%s'" % ', '.join(sorted(unique))

        # TODO: remove assertion in 2.1
        assert not hasattr(self, 'options'), \
            "The 'options' attribute has been replaced by 'choices' and 'filters'. " \
            "See: https://django-filter.readthedocs.io/en/master/guide/migration.html"

        # null choice not relevant
        kwargs.setdefault('null_label', None)
        super().__init__(choices=self.choices, *args, **kwargs)

    def filter(self, qs, value):
        if not value:
            return qs

        assert value in self.filters

        qs = self.filters[value](qs, self.field_name)
        return qs.distinct() if self.distinct else qs
    

class Ord_MastFilter(django_filters.FilterSet):

    DODATORD = k6DateRangeFilter(label=_("Data"))
        
    DONUMORDDA = django_filters.NumberFilter(label=_('Numerazione da'),field_name='DONUMORD', lookup_expr='gte')

    DONUMORDA = django_filters.NumberFilter(label=_('Numerazione a'),field_name='DONUMORD', lookup_expr='lte')

    DOALFORD = django_filters.CharFilter(lookup_expr='iexact',label=_('Serie'))

    CHOICEEVASI = {
        ('Aperti', _('Solo aperti')),
        ('Chiusi', _('Solo chiusi')),
        ('Tutti', _('Tutti')),        
    }


    ApertiEvasi = django_filters.ChoiceFilter(
                             choices=CHOICEEVASI,
                             method='filter_ApertiEvasi',
                             label=_('Stato')
                           )
    # se documento senza righe si considera non evadibile.
    def filter_ApertiEvasi(self, queryset, name, value):
        if value == 'Aperti':
            queryset = queryset.filter(DOCODICE__in=Subquery(Ord_dett.objects.filter(DOFLEVAS=0).values('DOCODICE')))

        if value == 'Chiusi':
            queryset = queryset.filter(DOCODICE__in=Subquery(Ord_dett.objects.filter(DOFLEVAS=1).values('DOCODICE')))

        return queryset.order_by('-DONUMORD').order_by('-DODATORD')   

    # imposto il valore iniziale per il filtro aperti evasi ad aperti    
    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data._mutable = True
            if 'ApertiEvasi' not in data:
                data['ApertiEvasi'] = 'Aperti'
            data._mutable = False
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = Ord_Mast
        fields = ['DOCODINT','DODATORD','DOALFORD']


class schedaScadenzaFilters(django_filters.FilterSet):

    # Filtri sul modello collegato ScadenzaPagamento
    SCCODICE__SCDATSCA = k6DateRangeFilter(label=_("Data Scadenza"))

    SCCODICE__DODATORD = k6DateRangeFilter(label=_("Data Documento"))
        
    DONUMORDDA = django_filters.NumberFilter(label=_('Num.Documento da'),field_name='SCCODICE__DONUMORD', lookup_expr='gte')

    DONUMORDA = django_filters.NumberFilter(label=_('Num.Documento a'),field_name='SCCODICE__DONUMORD', lookup_expr='lte')

    SCCODICE__DOALFORD = django_filters.CharFilter(lookup_expr='iexact',label=_('Serie'))

    SCTIPPAG = django_filters.ModelChoiceFilter(
        field_name="SCTIPPAG",
        queryset=MODPAGAM.objects.all(),
        empty_label=_("Tutti i Pagamenti"),
        label="Pagamenti",
    )

    intestatario = django_filters.ModelChoiceFilter(
        field_name="SCCODICE__DOCODINT",
        queryset=Nominativi.objects.none(), #nella _init_ imposto il filtro per intestatario
        empty_label=_("Tutti"),
        label="Intestatario",
        widget=autocomplete.ModelSelect2(
            url='nominativi-autocomplete/CLI', # è solo un place holder nella init e re impostato in base a quanto passato in data nella View
           
            attrs={
                'data-minimum-input-length': 3,
                'class': 'form-select'
            })
    )

    CHOICEEVASISCADENZE = {
        ('Aperti', _('Solo aperti')),
        ('Chiusi', _('Solo chiusi')),
    }


    ApertiEvasi = django_filters.ChoiceFilter(
                             choices=CHOICEEVASISCADENZE,
                             method='filter_ApertiEvasi',
                             label=_('Documenti Evasi'),
                             empty_label=_("Tutti"),
                           )
    # se documento senza righe si considera non evadibile.
    def filter_ApertiEvasi(self, queryset, name, value):
        if value == 'Aperti':
            queryset = queryset.filter(SCCODICE__DOCODICE__in=Subquery(Ord_dett.objects.filter(DOFLEVAS=0).values('DOCODICE')))

        if value == 'Chiusi':
            queryset = queryset.filter(SCCODICE__DOCODICE__in=Subquery(Ord_dett.objects.filter(DOFLEVAS=1).values('DOCODICE')))

        return queryset   

    pagata = django_filters.ChoiceFilter(
        field_name="SCPAGATA",
        choices=[
            ("N", "Aperti"),
            ("S", "Saldati"),
        ],
        label="Scadenza pagata",
        empty_label=_("Tutte"),
    )

    importo_scadenza = django_filters.RangeFilter(
        field_name="SCIMPSCA",
        label="Importo scadenza (range)"
    )

    class Meta:
        model = Scadenze
        fields = []   

    # imposto il valore iniziale per il filtro aperti evasi ad aperti    
    def __init__(self, data=None, *args, **kwargs):
        request = kwargs.get("request")
        if data is not None:
            data._mutable = True
            if 'pagata' not in data:
                data['pagata'] = 'N'
            
            data._mutable = False
        super().__init__(data, *args, **kwargs)

        if data:
            tipo = data.get("tipoIntestatario")  # <── QUI
            if tipo:
                url = f"/doc/nominativi-autocomplete/{tipo}"
                self.filters["intestatario"].field.widget.url = url


# filtro per la dashboard con le giacenze!
class DashboardFilter(django_filters.FilterSet):

    ARCODGRU = django_filters.ModelChoiceFilter(
        queryset=Grmemast.objects.all(),
        empty_label=_("Tutti i Gruppi"),
        label="Gruppi",
        )  

    class Meta:
        model = Articoli
        fields = ['ARCODGRU']

# filtro articoli!
class ArticoliFilter(django_filters.FilterSet):

    ARDESCRI = django_filters.CharFilter(lookup_expr='icontains',label=_('Descrizione'))

    ARCODICE = django_filters.CharFilter(lookup_expr='icontains',label=_('Codice'))

    class Meta:
        model = Articoli
        fields = ['ARCODICE','ARDESCRI']