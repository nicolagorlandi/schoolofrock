from calendar import monthrange
from datetime import date, time
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from dal import autocomplete

from PaNet1Project import settings
from documenti.models import Articoli, Causdocu, Nominativi

from .models import Alunno, Corso, Lezioni


class QuarterHourTimeSelect(forms.Select):
    def __init__(self, attrs=None):
        choices = [('', _('Seleziona un orario'))]
        choices.extend(
            (
                f'{hour:02d}:{minute:02d}',
                f'{hour:02d}:{minute:02d}',
            )
            for hour in range(24)
            for minute in (0, 15, 30, 45)
        )
        super().__init__(attrs, choices)

    def format_value(self, value):
        if isinstance(value, time):
            value = value.strftime('%H:%M')
        return super().format_value(value)


def validate_quarter_hour(value):
    if value.minute % 15 or value.second or value.microsecond:
        raise ValidationError(_('L’orario deve essere scelto a intervalli di 15 minuti.'))


class PeriodoLezioniForm(forms.Form):
    MESI = [
        (1, _('Gennaio')),
        (2, _('Febbraio')),
        (3, _('Marzo')),
        (4, _('Aprile')),
        (5, _('Maggio')),
        (6, _('Giugno')),
        (7, _('Luglio')),
        (8, _('Agosto')),
        (9, _('Settembre')),
        (10, _('Ottobre')),
        (11, _('Novembre')),
        (12, _('Dicembre')),
    ]

    anno = forms.IntegerField(
        label=_('Anno'),
        min_value=1900,
        max_value=9999,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1900, 'max': 9999}),
    )
    mese = forms.TypedChoiceField(
        label=_('Mese'),
        choices=MESI,
        coerce=int,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        oggi = date.today()
        mese_successivo = oggi.month % 12 + 1
        anno_mese_successivo = oggi.year + (oggi.month == 12)
        self.fields['anno'].initial = anno_mese_successivo
        self.fields['mese'].initial = mese_successivo


class PresenzeMensiliForm(PeriodoLezioniForm):
    corso = forms.ModelChoiceField(
        label=_('Corso'),
        queryset=Corso.objects.none(),
        required=False,
        empty_label=_('Tutti i corsi'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['corso'].queryset = Corso.objects.order_by(
            'descrizione',
            'pk',
        )


class IscrizioniForm(forms.Form):
    corso = forms.ModelChoiceField(
        label=_('Corso'),
        queryset=Corso.objects.none(),
        empty_label=_('Seleziona un corso'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    causale = forms.ModelChoiceField(
        label=_('Causale ricevuta fiscale'),
        queryset=Causdocu.objects.none(),
        empty_label=_('Seleziona una causale'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['corso'].queryset = Corso.objects.order_by(
            'descrizione',
            'pk',
        )
        self.fields['causale'].queryset = Causdocu.objects.filter(
            CDTIPDOC='RF'
        ).order_by('CDDESCRI', 'CDCODICE')


class FatturazioneForm(PeriodoLezioniForm):
    causale = forms.ModelChoiceField(
        label=_('Causale ricevuta fiscale'),
        queryset=Causdocu.objects.none(),
        empty_label=_('Seleziona una causale'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    alunno = forms.ModelChoiceField(
        label=_('Alunno'),
        queryset=Nominativi.objects.none(),
        required=False,
        empty_label=_('Tutti gli alunni'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    corso = forms.ModelChoiceField(
        label=_('Corso'),
        queryset=Corso.objects.none(),
        required=False,
        empty_label=_('Tutti i corsi'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['causale'].queryset = Causdocu.objects.filter(
            CDTIPDOC='RF'
        ).order_by('CDDESCRI', 'CDCODICE')
        anno = self['anno'].value()
        mese = self['mese'].value()
        try:
            anno = int(anno)
            mese = int(mese)
            inizio_periodo = date(anno, mese, 1)
            fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
        except (TypeError, ValueError):
            return

        self.fields['alunno'].queryset = Nominativi.objects.filter(
            corsi_frequentati__lezioni__data__range=(
                inizio_periodo,
                fine_periodo,
            )
        ).distinct().order_by('NORAGSOC')
        self.fields['corso'].queryset = Corso.objects.filter(
            alunni__lezioni__data__range=(inizio_periodo, fine_periodo)
        ).distinct().order_by('descrizione', 'pk')


class CorsoForm(forms.ModelForm):
    prezzo_iscrizione = forms.DecimalField(
        required=False,
        label=_('Prezzo iscrizione'),
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
    )

    class Meta:
        model = Corso
        fields = [
            'descrizione',
            'note',
            'durata_minuti',
            'di_gruppo',
            'calcoloCosto',
            'insegnante',
            'articolo',
            'prezzo',
            'prezzo_iscrizione',
            'costo',
            'data_inizio',
            'data_fine',
        ]
        labels = {
            'descrizione': _('Descrizione'),
            'note': _('Note'),
            'durata_minuti': _('Durata(minuti)'),
            'di_gruppo': _('Di gruppo'),
            'calcoloCosto': _('Forfettario'),
            'insegnante': _('Insegnante'),
            'articolo': _('Articolo per fatturazione'),
            'prezzo': _('Prezzo'),
            'prezzo_iscrizione': _('Prezzo iscrizione'),
            'costo': _('Costo'),
            'data_inizio': _('Data inizio'),
            'data_fine': _('Data fine'),
        }
        widgets = {
            'descrizione': forms.TextInput(attrs={'maxlength': 80}),
            'note': forms.Textarea(attrs={'rows': 4}),
            'durata_minuti': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'di_gruppo': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
            'calcoloCosto': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
            'insegnante': autocomplete.ModelSelect2(
                url='corsi:insegnante-autocomplete',
                attrs={'data-placeholder': _('Cerca un fornitore'), 'data-minimum-input-length': 2},
            ),
            'articolo': autocomplete.ModelSelect2(
                url='articoli-autocomplete',
                attrs={
                    'data-placeholder': _('Cerca un articolo'),
                    'data-minimum-input-length': 2,
                },
            ),
            'prezzo': forms.NumberInput(attrs={'step': '0.50', 'min': '0'}),
            'prezzo_iscrizione': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0'}
            ),
            'costo': forms.NumberInput(attrs={'step': '0.50', 'min': '0'}),
            'data_inizio': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
            ),
            'data_fine': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insegnante'].queryset = Nominativi.objects.filter(
            NOCODNOM=settings.CCATFOR
        ).order_by('NORAGSOC')
        self.fields['articolo'].queryset = Articoli.objects.order_by('ARDESCRI')

    def clean(self):
        cleaned_data = super().clean()
        if 'prezzo_iscrizione' not in self.data:
            cleaned_data['prezzo_iscrizione'] = (
                self.instance.prezzo_iscrizione
                if self.instance.pk
                else Decimal('0')
            )
        elif cleaned_data.get('prezzo_iscrizione') is None:
            cleaned_data['prezzo_iscrizione'] = Decimal('0')

        data_inizio = cleaned_data.get('data_inizio')
        data_fine = cleaned_data.get('data_fine')
        if data_inizio and data_fine and data_fine < data_inizio:
            self.add_error('data_fine', _('La data fine non può precedere la data inizio.'))
        return cleaned_data


class AlunnoForm(forms.ModelForm):
    ora_inizio = forms.TimeField(
        label=_('Ora inizio'),
        widget=QuarterHourTimeSelect(attrs={'class': 'form-select'}),
        validators=[validate_quarter_hour],
    )

    class Meta:
        model = Alunno
        fields = [
            'alunno',
            'prezzo',
            'giorno_settimana',
            'ora_inizio',
            'durata_minuti',
        ]
        labels = {
            'alunno': _('Alunno'),
            'prezzo': _('Prezzo'),
            'giorno_settimana': _('Giorno'),
            'durata_minuti': _('Durata (minuti)'),
        }
        widgets = {
            'alunno': autocomplete.ModelSelect2(
                url='corsi:alunno-autocomplete',
                attrs={'data-placeholder': _('Cerca un alunno'), 'data-minimum-input-length': 2},
            ),
            'prezzo': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0'}
            ),
            'durata_minuti': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        corso = getattr(self.instance, 'corso', None)
        if (
            not self.is_bound
            and not self.instance.pk
            and corso is not None
        ):
            self.initial.setdefault('durata_minuti', corso.durata_minuti)
        self.fields['alunno'].queryset = Nominativi.objects.filter(
            NOCODNOM=settings.CCATCLI
        ).order_by('NORAGSOC')


AlunnoFormSet = inlineformset_factory(
    Corso,
    Alunno,
    form=AlunnoForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
