from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, F, IntegerField, Prefetch, Q, Sum, Value, When
from django import forms
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from PaNet1Project import settings
from documenti.models import (
    Azienda,
    Nominativi,
    Ord_Mast,
    Ord_dett,
    Scadenze,
    Settings,
)
from documenti.services import finalizza_documento
import calendar
import locale

from .forms import (
    AlunnoFormSet,
    CorsoForm,
    FatturazioneForm,
    IscrizioniForm,
    PeriodoLezioniForm,
    PresenzeMensiliForm,
)
from .models import Alunno, Corso, Lezioni
from .permissions import is_insegnante


class NominativiAutocomplete(autocomplete.Select2QuerySetView):
    tipo_nominativo = None

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Nominativi.objects.none()

        nominativi = Nominativi.objects.filter(
            NOCODNOM=self.tipo_nominativo
        ).order_by('NORAGSOC')
        if self.q:
            nominativi = nominativi.filter(
                Q(NORAGSOC__icontains=self.q)
                | Q(NOCODICE__icontains=self.q)
                | Q(NOCOGNOM__icontains=self.q)
                | Q(NO_NOME__icontains=self.q)
            )
        return nominativi[:20]


class InsegnantiAutocomplete(NominativiAutocomplete):
    tipo_nominativo = settings.CCATFOR


class AlunniAutocomplete(NominativiAutocomplete):
    tipo_nominativo = settings.CCATCLI


def _importo_orario(minuti, tariffa_oraria):
    return (
        Decimal(minuti) * tariffa_oraria / Decimal('60')
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _ricavo_mensile_alunno(
    corso,
    durata_minuti_alunno,
    prezzo_alunno=None,
):
    if prezzo_alunno is not None:
        return prezzo_alunno.quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
    return (
        corso.prezzo
        * Decimal(durata_minuti_alunno)
        / Decimal(corso.durata_minuti) if corso.durata_minuti else Decimal(1)
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class CorsoFormsetMixin:
    model = Corso
    form_class = CorsoForm
    template_name = 'Corsi/corso_form.html'
    success_url = reverse_lazy('corsi:elenco')

    def get_formset(self):
        if not hasattr(self, '_formset'):
            corso = getattr(self, 'object', None) or Corso()
            self._formset = AlunnoFormSet(
                data=self.request.POST if self.request.method == 'POST' else None,
                instance=corso,
                queryset=Alunno.objects.select_related(
                    'alunno',
                    'ricevuta_iscrizione',
                ).order_by(
                    Case(
                        When(giorno_settimana='lunedi', then=Value(1)),
                        When(giorno_settimana='martedi', then=Value(2)),
                        When(giorno_settimana='mercoledi', then=Value(3)),
                        When(giorno_settimana='giovedi', then=Value(4)),
                        When(giorno_settimana='venerdi', then=Value(5)),
                        When(giorno_settimana='sabato', then=Value(6)),
                        When(giorno_settimana='domenica', then=Value(7)),
                        output_field=IntegerField(),
                    ),
                    'ora_inizio',
                    'alunno__NORAGSOC',
                ),
            )
        return self._formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = kwargs.get('formset', self.get_formset())
        return context

    def form_valid(self, form):
        formset = self.get_formset()
        if not formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        return self.render_to_response(
            self.get_context_data(
                form=form,
                formset=self.get_formset(),
                form_invalid=True,
            )
        )


@method_decorator(login_required, name='dispatch')
class CorsoCreateView(CorsoFormsetMixin, CreateView):
    pass


@method_decorator(login_required, name='dispatch')
class CorsoUpdateView(CorsoFormsetMixin, UpdateView):
    pass


@login_required
@require_POST
def duplica_corso(request, pk):
    corso_origine = get_object_or_404(Corso, pk=pk)
    campi_corso = {
        field.attname: getattr(corso_origine, field.attname)
        for field in Corso._meta.concrete_fields
        if not field.primary_key
    }
    righe_alunni = list(corso_origine.alunni.all())

    with transaction.atomic():
        corso_duplicato = Corso.objects.create(**campi_corso)
        Alunno.objects.bulk_create([
            Alunno(
                corso=corso_duplicato,
                **{
                    field.attname: getattr(riga, field.attname)
                    for field in Alunno._meta.concrete_fields
                    if not field.primary_key and field.name != 'corso'
                },
            )
            for riga in righe_alunni
        ])

    return redirect('corsi:modifica', pk=corso_duplicato.pk)


@method_decorator(login_required, name='dispatch')
class CorsoDeleteView(DeleteView):
    model = Corso
    template_name = 'Corsi/corso_confirm_delete.html'
    success_url = reverse_lazy('corsi:elenco')


@login_required
def elenco_corsi(request):
    corsi = Corso.objects.select_related(
        'insegnante',
        'articolo',
    ).prefetch_related(
        Prefetch('alunni', queryset=Alunno.objects.select_related('alunno'))
    )
    return render(request, 'Corsi/corso_list.html', {'corsi': corsi})


@login_required
def calendario_lezioni(request):
    corsi = Corso.objects.select_related('insegnante').order_by('insegnante__NORAGSOC')
    alunni = Nominativi.objects.filter(
        pk__in=Alunno.objects.values('alunno_id')
    ).order_by('NORAGSOC')
    return render(
        request,
        'Corsi/calendario_lezioni.html',
        {
            'corsi': corsi,
            'alunni': alunni,
            'eventi_url': reverse('corsi:calendario-eventi'),
            'is_insegnante': is_insegnante(request.user),
        },
    )


@login_required
@require_http_methods(['GET'])
def eventi_calendario(request):
    try:
        inizio = date.fromisoformat(request.GET['start'][:10])
        fine = date.fromisoformat(request.GET['end'][:10])
    except (KeyError, ValueError):
        return JsonResponse(
            {'error': 'Intervallo del calendario non valido.'},
            status=400,
        )

    if fine <= inizio:
        return JsonResponse(
            {'error': 'Intervallo del calendario non valido.'},
            status=400,
        )

    lezioni = Lezioni.objects.filter(
        data__gte=inizio,
        data__lt=fine,
    ).select_related(
        'alunno__corso',
        'alunno__alunno',
    )
    corso_id = request.GET.get('corso')
    alunno_id = request.GET.get('alunno')
    if corso_id:
        if not corso_id.isdecimal():
            return JsonResponse({'error': 'Corso non valido.'}, status=400)
        lezioni = lezioni.filter(alunno__corso_id=corso_id)
    if alunno_id:
        lezioni = lezioni.filter(alunno__alunno_id=alunno_id)

    eventi = []
    for lezione in lezioni.order_by('data', 'alunno__ora_inizio').iterator():
        ora_inizio = lezione.ora_inizio or lezione.alunno.ora_inizio
        durata_minuti = (
            lezione.durata_minuti or lezione.alunno.durata_minuti
        )
        inizio_lezione = datetime.combine(lezione.data, ora_inizio)
        fine_lezione = inizio_lezione + timedelta(
            minutes=durata_minuti
        )
        eventi.append(
            {
                'id': lezione.pk,
                'title': lezione.alunno.alunno.NORAGSOC or str(lezione.alunno.alunno),
                'start': inizio_lezione.isoformat(),
                'end': fine_lezione.isoformat(),
                'resourceId': str(lezione.alunno.corso_id),
                'backgroundColor': '#198754' if lezione.presenza else '#6c757d',
                'borderColor': '#198754' if lezione.presenza else '#6c757d',
                'extendedProps': {
                    'presenza': lezione.presenza,
                    'corso': str(lezione.alunno.corso.descrizione),
                    'alunno': str(lezione.alunno.alunno),
                    'note': lezione.note,
                    'durata_minuti': durata_minuti,
                },
            }
        )
    return JsonResponse(eventi, safe=False)


@login_required
@require_POST
def aggiorna_presenza_lezione(request, pk):
    presenza = request.POST.get('presenza')
    if presenza not in {'true', 'false'}:
        return JsonResponse(
            {'error': 'Valore della presenza non valido.'},
            status=400,
        )

    lezione = get_object_or_404(Lezioni, pk=pk)
    lezione.presenza = presenza == 'true'
    lezione.save(update_fields=['presenza'])
    return JsonResponse({'id': lezione.pk, 'presenza': lezione.presenza})


@login_required
@require_POST
def modifica_orario_lezione(request, pk):
    try:
        data_lezione = date.fromisoformat(request.POST['data'])
        ora_inizio = datetime.strptime(request.POST['ora_inizio'], '%H:%M').time()
    except (KeyError, ValueError):
        return JsonResponse(
            {'error': 'Data o orario della lezione non validi.'},
            status=400,
        )

    durata_minuti = None
    if 'durata_minuti' in request.POST:
        valore_durata = request.POST['durata_minuti']
        if not valore_durata.isdecimal() or int(valore_durata) < 1:
            return JsonResponse(
                {'error': 'La durata della lezione non è valida.'},
                status=400,
            )
        durata_minuti = int(valore_durata)

    lezione = get_object_or_404(Lezioni, pk=pk)
    lezione.data = data_lezione
    lezione.ora_inizio = ora_inizio
    update_fields = ['data', 'ora_inizio']
    if durata_minuti is not None:
        lezione.durata_minuti = durata_minuti
        update_fields.append('durata_minuti')
    lezione.save(update_fields=update_fields)
    return JsonResponse(
        {
            'id': lezione.pk,
            'data': lezione.data.isoformat(),
            'ora_inizio': lezione.ora_inizio.strftime('%H:%M'),
            'durata_minuti': (
                lezione.durata_minuti or lezione.alunno.durata_minuti
            ),
        }
    )


def date_lezioni_alunno(alunno, inizio_periodo, fine_periodo):
    giorno_settimana = next(
        index
        for index, (codice, _) in enumerate(Alunno.GIORNI_SETTIMANA)
        if codice == alunno.giorno_settimana
    )
    primo_giorno = inizio_periodo + timedelta(
        days=(giorno_settimana - inizio_periodo.weekday()) % 7
    )
    while primo_giorno <= fine_periodo:
        yield primo_giorno
        primo_giorno += timedelta(days=7)


@login_required
@require_http_methods(['GET', 'POST'])
def gestione_lezioni(request):
    if request.method == 'POST':
        form = PeriodoLezioniForm(request.POST)
        periodo_valido = form.is_valid()
    elif request.GET:
        form = PeriodoLezioniForm(request.GET)
        periodo_valido = form.is_valid()
    else:
        form = PeriodoLezioniForm()
        anno_default = form.fields['anno'].initial
        mese_default = form.fields['mese'].initial
        form = PeriodoLezioniForm(
            {'anno': anno_default, 'mese': mese_default}
        )
        periodo_valido = form.is_valid()

    if periodo_valido:
        anno = form.cleaned_data['anno']
        mese = form.cleaned_data['mese']
    else:
        anno = mese = None

    corsi = Corso.objects.none()
    inizio_periodo = fine_periodo = None
    if anno is not None and mese is not None:
        inizio_periodo = date(anno, mese, 1)
        fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
        corsi = Corso.objects.filter(
            data_inizio__lte=fine_periodo,
            data_fine__gte=inizio_periodo,
        ).select_related('insegnante').prefetch_related(
            Prefetch('alunni', queryset=Alunno.objects.select_related('alunno'))
        )

    if (
        request.method == 'POST'
        and periodo_valido
        and 'elimina_corso' in request.POST
    ):
        corso_id = request.POST['elimina_corso']
        query = urlencode({'anno': anno, 'mese': mese})
        redirect_url = f'{reverse("corsi:lezioni")}?{query}'
        if not corso_id.isdecimal():
            messages.error(request, 'La selezione del corso non è valida.')
            return redirect(redirect_url)

        corso = corsi.filter(pk=int(corso_id)).first()
        if corso is None:
            messages.error(
                request,
                'Il corso selezionato non appartiene al periodo indicato.',
            )
            return redirect(redirect_url)

        lezioni_periodo = Lezioni.objects.filter(
            alunno__corso=corso,
        ).filter(
            Q(data_ricorrenza__range=(inizio_periodo, fine_periodo))
            | Q(
                data_ricorrenza__isnull=True,
                data__range=(inizio_periodo, fine_periodo),
            )
        )
        with transaction.atomic():
            lezioni_protette = lezioni_periodo.filter(
                Q(presenza=True)
                | Q(documento_fatturazione__isnull=False)
            ).count()
            lezioni_eliminabili = lezioni_periodo.filter(
                presenza=False,
                documento_fatturazione__isnull=True,
            )
            lezioni_eliminate, _ = lezioni_eliminabili.delete()

        if lezioni_eliminate:
            messages.success(
                request,
                f'Lezioni eliminate: {lezioni_eliminate} per il corso '
                f'{corso}.',
            )
        if lezioni_protette:
            messages.warning(
                request,
                f'{lezioni_protette} lezioni sono state mantenute '
                'perché contrassegnate come presenti o collegate a una '
                'ricevuta.',
            )
        if not lezioni_eliminate and not lezioni_protette:
            messages.info(
                request,
                'Non ci sono lezioni da eliminare per il corso nel mese '
                'selezionato.',
            )
        return redirect(redirect_url)

    if request.method == 'POST' and periodo_valido:
        corso_singolo = request.POST.get('corso_singolo')
        selezionati = (
            [corso_singolo]
            if corso_singolo
            else request.POST.getlist('corsi_selezionati')
        )
        if not selezionati:
            messages.error(request, 'Seleziona almeno un corso da elaborare.')
        elif any(not corso_id.isdecimal() for corso_id in selezionati):
            messages.error(request, 'La selezione dei corsi non è valida.')
        else:
            ids_selezionati = [int(corso_id) for corso_id in selezionati]
            corsi_selezionati = list(corsi.filter(pk__in=ids_selezionati))
            if len(corsi_selezionati) != len(set(ids_selezionati)):
                messages.error(
                    request,
                    'Uno o più corsi selezionati non appartengono al periodo indicato.',
                )
            else:
                lezioni_da_creare = []
                lezioni_esistenti = 0
                for corso in corsi_selezionati:
                    righe_alunno = Alunno.objects.filter(corso=corso).prefetch_related(
                        Prefetch(
                            'lezioni',
                            queryset=Lezioni.objects.filter(
                                Q(
                                    data_ricorrenza__range=(
                                        inizio_periodo,
                                        fine_periodo,
                                    )
                                )
                                | Q(
                                    data_ricorrenza__isnull=True,
                                    data__range=(inizio_periodo, fine_periodo),
                                )
                            ).only('alunno_id', 'data', 'data_ricorrenza'),
                        )
                    ).iterator()
                    for riga in righe_alunno:
                        date_esistenti = {
                            lezione.data_ricorrenza or lezione.data
                            for lezione in riga.lezioni.all()
                        }
                        for data_lezione in date_lezioni_alunno(
                            riga, inizio_periodo, fine_periodo
                        ):
                            if not corso.data_inizio <= data_lezione <= corso.data_fine:
                                continue
                            if data_lezione in date_esistenti:
                                lezioni_esistenti += 1
                            else:
                                lezioni_da_creare.append(
                                    Lezioni(
                                        alunno=riga,
                                        data=data_lezione,
                                        data_ricorrenza=data_lezione,
                                    )
                                )

                if lezioni_da_creare:
                    Lezioni.objects.bulk_create(lezioni_da_creare)
                messages.success(
                    request,
                    f"Generate {len(lezioni_da_creare)} lezioni; "
                    f"{lezioni_esistenti} già esistenti non sono state duplicate.",
                )
                query = urlencode({'anno': anno, 'mese': mese})
                return redirect(f'{reverse("corsi:lezioni")}?{query}')

    context = {
        'form': form,
        'corsi': corsi,
        'anno': anno,
        'mese': mese,
        'form_invalid': not periodo_valido,
    }
    return render(request, 'Corsi/lezioni.html', context)


@login_required
@require_http_methods(['GET'])
def presenze_mensili(request):
    if request.GET:
        form = PresenzeMensiliForm(request.GET)
    else:
        form_iniziale = PresenzeMensiliForm()
        form = PresenzeMensiliForm(
            {
                'anno': form_iniziale.fields['anno'].initial,
                'mese': form_iniziale.fields['mese'].initial,
            }
        )

    dettaglio_lezioni = []
    riepilogo_corsi = []
    riepilogo_alunni = []
    totali = None

    if form.is_valid():
        anno = form.cleaned_data['anno']
        mese = form.cleaned_data['mese']
        corso = form.cleaned_data['corso']
        inizio_periodo = date(anno, mese, 1)
        fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
        lezioni = Lezioni.objects.filter(
            data__range=(inizio_periodo, fine_periodo)
        )
        if corso is not None:
            lezioni = lezioni.filter(alunno__corso=corso)
        lezioni = lezioni.select_related(
            'alunno__corso__insegnante',
            'alunno__alunno',
        ).order_by(
            'alunno__corso__insegnante__NORAGSOC',
            'alunno__corso_id',
            'alunno__alunno__NORAGSOC',
            'data',
            'ora_inizio',
            'alunno__ora_inizio',
        ).iterator()

        corsi_per_id = {}
        alunni_per_chiave = {}
        slot_corso_contati = set()
        for lezione in lezioni:
            riga_alunno = lezione.alunno
            corso = riga_alunno.corso
            nominativo = riga_alunno.alunno
            durata = lezione.durata_minuti or riga_alunno.durata_minuti
            ora_inizio = lezione.ora_inizio or riga_alunno.ora_inizio
            dettaglio_lezioni.append(
                {
                    'lezione': lezione,
                    'corso': corso,
                    'docente': corso.insegnante,
                    'alunno': nominativo,
                    'ora_inizio': ora_inizio,
                    'durata_minuti': durata,
                    'ore': Decimal(durata) / Decimal('60'),
                }
            )

            riepilogo_corso = corsi_per_id.setdefault(
                corso.pk,
                {
                    'corso': corso,
                    'minuti': 0,
                    'costo': Decimal('0.00'),
                    'ricavo': Decimal('0.00'),
                },
            )
            # Nei corsi di gruppo conto una volta lo stesso slot e la stessa durata.
            slot_corso = (corso.pk, lezione.data, ora_inizio, durata)
            if not corso.di_gruppo:
                riepilogo_corso['minuti'] += durata
            elif slot_corso not in slot_corso_contati:
                riepilogo_corso['minuti'] += durata
                slot_corso_contati.add(slot_corso)

            chiave_alunno = (corso.pk, nominativo.pk)
            riepilogo_alunno = alunni_per_chiave.setdefault(
                chiave_alunno,
                {
                    'corso': corso,
                    'alunno': nominativo,
                    'durata_minuti_configurata_alunno': riga_alunno.durata_minuti,
                    'minuti': 0,
                    'minuti_assenza': 0,
                    'ricavo': Decimal('0.00'),
                },
            )
            riepilogo_alunno['minuti'] += durata
            if not lezione.presenza:
                riepilogo_alunno['minuti_assenza'] += durata

        for riepilogo_alunno in alunni_per_chiave.values():
            corso = riepilogo_alunno['corso']
            riepilogo_alunno['ricavo'] = _ricavo_mensile_alunno(
                corso,
                riepilogo_alunno['durata_minuti_configurata_alunno'],
            )
            corsi_per_id[corso.pk]['ricavo'] += riepilogo_alunno['ricavo']

        for riepilogo_corso in corsi_per_id.values():
            corso = riepilogo_corso['corso']
            if corso.calcoloCosto:
                riepilogo_corso['costo'] = corso.costo
            else:
                riepilogo_corso['costo'] = _importo_orario(
                    riepilogo_corso['minuti'],
                    corso.costo,
                )
            riepilogo_corso['ore'] = (
                Decimal(riepilogo_corso['minuti']) / Decimal('60')
            )
            riepilogo_corso['differenza'] = (
                riepilogo_corso['ricavo'] - riepilogo_corso['costo']
            )
            riepilogo_corsi.append(riepilogo_corso)

        riepilogo_alunni = sorted(
            alunni_per_chiave.values(),
            key=lambda riepilogo: (
                riepilogo['alunno'].NORAGSOC or '',
                riepilogo['corso'].insegnante.NORAGSOC or '',
                riepilogo['corso'].pk or '',
            ),
        )
        for riepilogo_alunno in riepilogo_alunni:
            riepilogo_alunno['ore'] = (
                Decimal(riepilogo_alunno['minuti']) / Decimal('60')
            )
            riepilogo_alunno['ore_assenza'] = (
                Decimal(riepilogo_alunno['minuti_assenza'])
                / Decimal('60')
            )
        totali = {
            'minuti_costo': sum(r['minuti'] for r in riepilogo_corsi),
            'ore_costo': (
                Decimal(sum(r['minuti'] for r in riepilogo_corsi))
                / Decimal('60')
            ),
            'costo': sum(
                (r['costo'] for r in riepilogo_corsi),
                Decimal('0.00'),
            ),
            'ricavo': sum(
                (r['ricavo'] for r in riepilogo_corsi),
                Decimal('0.00'),
            ),
            'differenza': sum(
                (r['differenza'] for r in riepilogo_corsi),
                Decimal('0.00'),
            ),
            'minuti_alunni': sum(r['minuti'] for r in riepilogo_alunni),
            'ore_alunni': (
                Decimal(sum(r['minuti'] for r in riepilogo_alunni))
                / Decimal('60')
            ),
            'minuti_assenza': sum(
                r['minuti_assenza'] for r in riepilogo_alunni
            ),
            'ore_assenza': (
                Decimal(
                    sum(r['minuti_assenza'] for r in riepilogo_alunni)
                )
                / Decimal('60')
            ),
        }

    return render(
        request,
        'Corsi/presenze_mensili.html',
        {
            'form': form,
            'anno': form.cleaned_data.get('anno') if form.is_valid() else None,
            'mese': form.cleaned_data.get('mese') if form.is_valid() else None,
            'dettaglio_lezioni': dettaglio_lezioni,
            'riepilogo_corsi': riepilogo_corsi,
            'riepilogo_alunni': riepilogo_alunni,
            'totali': totali,
        },
    )


def _lezioni_fatturazione_periodo(
    inizio_periodo,
    fine_periodo,
    alunno=None,
    corso=None,
):
    lezioni = Lezioni.objects.filter(
        data__range=(inizio_periodo, fine_periodo)
    )
    if corso:
        alunni_con_corso = lezioni.filter(
            alunno__corso=corso
        ).values_list('alunno__alunno_id', flat=True).distinct()
        lezioni = lezioni.filter(alunno__alunno_id__in=alunni_con_corso)
    if alunno:
        lezioni = lezioni.filter(alunno__alunno=alunno)
    return lezioni


def _elimina_ricevute(request, documento_ids):
    form = FatturazioneForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Selezionare un periodo e una causale validi.')
        return redirect('corsi:fatturazione')

    anno = form.cleaned_data['anno']
    mese = form.cleaned_data['mese']
    causale = form.cleaned_data['causale']
    alunno = form.cleaned_data['alunno']
    corso = form.cleaned_data['corso']
    redirect_response = _redirect_fatturazione(
        anno, mese, causale, alunno, corso
    )

    if not documento_ids:
        messages.error(request, 'Selezionare almeno una ricevuta da eliminare.')
        return redirect_response

    if any(not documento_id.isdecimal() for documento_id in documento_ids):
        messages.error(request, 'La selezione delle ricevute non è valida.')
        return redirect_response

    documento_ids = {int(documento_id) for documento_id in documento_ids}
    inizio_periodo = date(anno, mese, 1)
    fine_periodo = date(anno, mese, monthrange(anno, mese)[1])

    with transaction.atomic():
        lezioni = _lezioni_fatturazione_periodo(
            inizio_periodo,
            fine_periodo,
            alunno=alunno,
            corso=corso,
        )
        documenti_validi = set(
            lezioni.filter(
                documento_fatturazione__DOTIPDOC='RF',
            ).values_list('documento_fatturazione_id', flat=True).distinct()
        )
        if not documento_ids.issubset(documenti_validi):
            messages.error(
                request,
                'Una o più ricevute selezionate non appartengono alla '
                'fatturazione visualizzata.',
            )
            return redirect_response

        documenti = list(
            Ord_Mast.objects.select_for_update().filter(
                pk__in=documento_ids,
                DOTIPDOC='RF',
            )
        )
        if len(documenti) != len(documento_ids):
            messages.error(request, 'Una o più ricevute non sono più disponibili.')
            return redirect_response

        for documento in documenti:
            documento.delete()

    messages.success(
        request,
        f'Eliminate {len(documento_ids)} ricevute fiscali.',
    )
    return redirect_response


@login_required
@require_POST
def elimina_ricevuta(request, documento_id):
    return _elimina_ricevute(request, [str(documento_id)])


@login_required
@require_POST
def elimina_ricevute_selezionate(request):
    return _elimina_ricevute(
        request,
        request.POST.getlist('documenti_ids'),
    )


@login_required
@require_http_methods(['GET'])
def fatturazione_mensile(request):
    form = FatturazioneForm(request.GET or None)
    righe_fatturazione = []
    totale_documenti_pagati = Decimal('0.00')
    totale_documenti_non_pagati = Decimal('0.00')
    totale_corsi_da_pagare = Decimal('0.00')
    if form.is_valid():
        anno = form.cleaned_data['anno']
        mese = form.cleaned_data['mese']
        inizio_periodo = date(anno, mese, 1)
        fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
        lezioni = _lezioni_fatturazione_periodo(
            inizio_periodo,
            fine_periodo,
            alunno=form.cleaned_data['alunno'],
            corso=form.cleaned_data['corso'],
        ).select_related(
            'alunno__alunno',
            'alunno__corso__articolo',
            'documento_fatturazione',
        ).order_by(
            'alunno__alunno__NORAGSOC',
            'alunno__corso__descrizione',
            'alunno__corso_id',
            'data',
        ).iterator()

        righe_per_alunno = {}
        for lezione in lezioni:
            alunno = lezione.alunno.alunno
            riepilogo = righe_per_alunno.setdefault(
                alunno.pk,
                {
                    'alunno': alunno,
                    'corsi_per_id': {},
                    'documenti': set(),
                    'ricevute_fiscali': set(),
                    'numero_lezioni': 0,
                    'numero_lezioni_fatturate': 0,
                },
            )
            riepilogo['numero_lezioni'] += 1
            if lezione.documento_fatturazione_id:
                riepilogo['numero_lezioni_fatturate'] += 1
                riepilogo['documenti'].add(lezione.documento_fatturazione_id)
                if lezione.documento_fatturazione.DOTIPDOC == 'RF':
                    riepilogo['ricevute_fiscali'].add(
                        lezione.documento_fatturazione_id
                    )

            corso = lezione.alunno.corso
            corso_riepilogo = riepilogo['corsi_per_id'].setdefault(
                corso.pk,
                {
                    'corso': corso,
                    'durata_minuti_alunno': lezione.alunno.durata_minuti,
                    'prezzo_alunno': lezione.alunno.prezzo,
                    'minuti': 0,
                },
            )
            corso_riepilogo['minuti'] += (
                lezione.durata_minuti or lezione.alunno.durata_minuti
            )

        documenti_ids = {
            documento_id
            for riepilogo in righe_per_alunno.values()
            for documento_id in riepilogo['documenti']
        }
        scadenze_per_documento = {}
        for scadenza in Scadenze.objects.filter(
            SCCODICE_id__in=documenti_ids
        ).order_by('SCNUMSCA', 'pk').iterator():
            scadenze_per_documento.setdefault(
                scadenza.SCCODICE_id, []
            ).append(scadenza)
        totali_per_documento = {
            risultato['DOCODICE_id']: risultato['totale'] or Decimal('0.00')
            for risultato in Ord_dett.objects.filter(
                DOCODICE_id__in=documenti_ids
            ).values('DOCODICE_id').annotate(
                totale=Sum(F('DOPREZZO') * F('DOQTAUM1'))
            )
        }

        for riepilogo in righe_per_alunno.values():
            corsi_riepilogo = []
            totale = Decimal('0.00')
            articolo_mancante = False
            for corso_riepilogo in riepilogo['corsi_per_id'].values():
                corso = corso_riepilogo['corso']
                importo = _ricavo_mensile_alunno(
                    corso,
                    corso_riepilogo['durata_minuti_alunno'],
                    corso_riepilogo['prezzo_alunno'],
                )
                totale += importo
                articolo_mancante = (
                    articolo_mancante or corso.articolo_id is None
                )
                corsi_riepilogo.append(
                    {
                        'corso': corso,
                        'minuti': corso_riepilogo['minuti'],
                        'importo': importo,
                    }
                )

            corsi_riepilogo.sort(
                key=lambda riga: str(riga['corso']).casefold()
            )
            totale_corsi_da_pagare += totale
            fatturata = (
                riepilogo['numero_lezioni_fatturate']
                == riepilogo['numero_lezioni']
                and len(riepilogo['documenti']) == 1
            )
            fatturazione_parziale = (
                riepilogo['numero_lezioni_fatturate'] > 0 and not fatturata
            )
            documento_id = (
                next(iter(riepilogo['documenti'])) if fatturata else None
            )
            eliminabile = documento_id in riepilogo['ricevute_fiscali']
            scadenze = (
                scadenze_per_documento.get(documento_id, [])
                if documento_id
                else []
            )
            pagato = bool(scadenze) and all(
                scadenza.SCPAGATA == 'S' for scadenza in scadenze
            )
            totale_documento = (
                totali_per_documento.get(documento_id, Decimal('0.00'))
                if documento_id
                else None
            )
            if totale_documento is not None:
                if pagato:
                    totale_documenti_pagati += totale_documento
                else:
                    totale_documenti_non_pagati += totale_documento
            righe_fatturazione.append(
                {
                    'alunno': riepilogo['alunno'],
                    'corsi': corsi_riepilogo,
                    'totale': totale,
                    'documento_id': documento_id,
                    'eliminabile': eliminabile,
                    'totale_documento': totale_documento,
                    'scadenze': scadenze,
                    'pagato': pagato,
                    'scadenze_non_pagate': [
                        scadenza for scadenza in scadenze
                        if scadenza.SCPAGATA != 'S'
                    ],
                    'fatturazione_parziale': fatturazione_parziale,
                    'articolo_mancante': articolo_mancante,
                    'generabile': not (
                        fatturata or fatturazione_parziale or articolo_mancante
                    ),
                }
            )

    return render(
        request,
        'Corsi/fatturazione.html',
        {
            'form': form,
            'righe_fatturazione': righe_fatturazione,
            'numero_ricevute_generabili': sum(
                riga['generabile'] for riga in righe_fatturazione
            ),
            'numero_ricevute_eliminabili': sum(
                riga['eliminabile']
                for riga in righe_fatturazione
            ),
            'totale_documenti_pagati': totale_documenti_pagati,
            'totale_documenti_non_pagati': totale_documenti_non_pagati,
            'totale_corsi_da_pagare': totale_corsi_da_pagare,
            'anno': form.cleaned_data.get('anno') if form.is_valid() else None,
            'mese': form.cleaned_data.get('mese') if form.is_valid() else None,
            'causale': form.cleaned_data.get('causale') if form.is_valid() else None,
        },
    )


def _crea_ricevuta_alunno(
    nominativo,
    causale,
    inizio_periodo,
    fine_periodo,
    utente,
):
    with transaction.atomic():
        lezioni = list(
            Lezioni.objects.select_for_update(of=('self',)).filter(
                alunno__alunno=nominativo,
                data__range=(inizio_periodo, fine_periodo),
            ).select_related(
                'alunno__corso__articolo',
                'alunno__alunno',
                'documento_fatturazione',
            ).order_by('alunno__corso_id', 'data', 'pk')
        )
        if not lezioni:
            raise ValidationError(
                'Non ci sono lezioni da fatturare per l’alunno nel mese selezionato.'
            )
        if any(lezione.documento_fatturazione_id for lezione in lezioni):
            raise ValidationError(
                'Una o più lezioni del mese risultano già collegate a una ricevuta.'
            )

        corsi_per_id = {}
        for lezione in lezioni:
            corso = lezione.alunno.corso
            if corso.articolo_id is None:
                raise ValidationError(
                    f'Il corso "{corso}" non ha un articolo di fatturazione associato.'
                )
            corsi_per_id.setdefault(
                corso.pk,
                {
                    'corso': corso,
                    'durata_minuti_alunno': lezione.alunno.durata_minuti,
                    'prezzo_alunno': lezione.alunno.prezzo,
                },
            )

        data_documento = timezone.localtime(timezone.now()).date()
        serie = str(data_documento.year)
        numero = 0
        if causale.CDNUMAUT == 1:
            numeri_esistenti = Ord_Mast.objects.select_for_update().filter(
                DOALFORD=serie,
                DOCODCAU__CDTIPDOC='RF',
                DONUMORD__isnull=False,
            ).values_list('DONUMORD', flat=True)
            numero = max(numeri_esistenti, default=0) + 1
        else:
            serie = None

        locale.setlocale(locale.LC_TIME, "it_IT.UTF-8")
        mese = calendar.month_name[lezione.data.month]

        documento = Ord_Mast.objects.create(
            DONUMORD=numero,
            DOALFORD=serie,
            DODATORD=data_documento,
            DOCODCAU=causale,
            DOCODPAG=causale.CDPAGDEF or Settings.get_settings().AZPAGDEF,
            DOCODINT=nominativo,
            DOCODUTE=utente,
            DOTIPDOC='RF',
            DONOTE = f'Scuola di Musica mese di {mese}',
            slug=slugify(
                f'ricevuta-{causale.CDCODICE}-{data_documento}-{numero}'
            ),
        )
        for numero_riga, riepilogo in enumerate(corsi_per_id.values(), start=1):
            corso = riepilogo['corso']
            Ord_dett.objects.create(
                DOCODICE=documento,
                DONUMRIG=numero_riga,
                DOCODART=corso.articolo,
                DOQTAUM1=Decimal('1'),
                DOPREZZO=_ricavo_mensile_alunno(
                    corso,
                    riepilogo['durata_minuti_alunno'],
                    riepilogo['prezzo_alunno'],
                ),
                DODESART=str(corso),
            )

        form_post_salvataggio = forms.Form()
        finalizza_documento(
            documento,
            form_post_salvataggio,
            acconto=documento.DOIMPACC,
            finanziamento=documento.DOIMPFIN,
        )
        if form_post_salvataggio.errors:
            raise ValidationError(
                list(form_post_salvataggio.non_field_errors())
            )

        Lezioni.objects.filter(
            pk__in=[lezione.pk for lezione in lezioni]
        ).update(documento_fatturazione=documento)

    return documento


def _redirect_fatturazione(anno, mese, causale, alunno=None, corso=None):
    parametri = {
        'anno': anno,
        'mese': mese,
        'causale': causale.pk,
    }
    if alunno:
        parametri['alunno'] = alunno.pk
    if corso:
        parametri['corso'] = corso.pk
    query = urlencode(parametri)
    return redirect(f'{reverse("corsi:fatturazione")}?{query}')


def _crea_ricevuta_iscrizione(iscrizione, causale, utente):
    with transaction.atomic():
        iscrizione = get_object_or_404(
            Alunno.objects.select_for_update().select_related(
                'alunno',
                'corso',
            ),
            pk=iscrizione.pk,
        )
        if iscrizione.ricevuta_iscrizione_id:
            raise ValidationError(
                'L’iscrizione ha già una ricevuta fiscale collegata.'
            )

        azienda = Azienda.get_azienda()
        if azienda.AZARTINS_id is None:
            raise ValidationError(
                'Configurare in Azienda l’articolo per l’iscrizione.'
            )
        if azienda.AZARTTES_id is None:
            raise ValidationError(
                'Configurare in Azienda l’articolo per la tessera.'
            )

        data_documento = timezone.localtime(timezone.now()).date()
        serie = str(data_documento.year)
        numero = 0
        if causale.CDNUMAUT == 1:
            numeri_esistenti = Ord_Mast.objects.select_for_update().filter(
                DOALFORD=serie,
                DOCODCAU__CDTIPDOC='RF',
                DONUMORD__isnull=False,
            ).values_list('DONUMORD', flat=True)
            numero = max(numeri_esistenti, default=0) + 1
        else:
            serie = None

        documento = Ord_Mast.objects.create(
            DONUMORD=numero,
            DOALFORD=serie,
            DODATORD=data_documento,
            DOCODCAU=causale,
            DOCODPAG=causale.CDPAGDEF or Settings.get_settings().AZPAGDEF,
            DOCODINT=iscrizione.alunno,
            DOCODUTE=utente,
            DOTIPDOC='RF',
            DONOTE=f'Iscrizione al corso {iscrizione.corso}',
            slug=slugify(
                f'iscrizione-{iscrizione.pk}-{data_documento}-{numero}'
            ),
        )
        Ord_dett.objects.create(
            DOCODICE=documento,
            DONUMRIG=1,
            DOCODART=azienda.AZARTINS,
            DOQTAUM1=Decimal('1'),
            DOPREZZO=iscrizione.corso.prezzo_iscrizione,
            DODESART=f'Quota iscrizione - {iscrizione.corso}',
        )
        Ord_dett.objects.create(
            DOCODICE=documento,
            DONUMRIG=2,
            DOCODART=azienda.AZARTTES,
            DOQTAUM1=Decimal('1'),
            DOPREZZO=azienda.AZARTTES.ARPREZZO or Decimal('0'),
            DODESART='Tessera associativa',
        )

        form_post_salvataggio = forms.Form()
        finalizza_documento(
            documento,
            form_post_salvataggio,
            acconto=documento.DOIMPACC,
            finanziamento=documento.DOIMPFIN,
        )
        if form_post_salvataggio.errors:
            raise ValidationError(
                list(form_post_salvataggio.non_field_errors())
            )

        iscrizione.ricevuta_iscrizione = documento
        iscrizione.save(update_fields=['ricevuta_iscrizione'])

    return documento


def _redirect_iscrizioni(corso, causale):
    query = urlencode({
        'corso': corso.pk,
        'causale': causale.pk,
    })
    return redirect(f'{reverse("corsi:iscrizioni")}?{query}')


def _elimina_ricevute_iscrizione(request, iscrizione_ids):
    form = IscrizioniForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Selezionare un corso e una causale validi.')
        return redirect('corsi:iscrizioni')

    corso = form.cleaned_data['corso']
    causale = form.cleaned_data['causale']
    redirect_response = _redirect_iscrizioni(corso, causale)

    if not iscrizione_ids:
        messages.error(
            request,
            'Selezionare almeno una ricevuta di iscrizione da eliminare.',
        )
        return redirect_response
    if any(not iscrizione_id.isdecimal() for iscrizione_id in iscrizione_ids):
        messages.error(request, 'La selezione delle iscrizioni non è valida.')
        return redirect_response

    iscrizione_ids = {int(iscrizione_id) for iscrizione_id in iscrizione_ids}
    with transaction.atomic():
        iscrizioni = list(
            Alunno.objects.select_for_update(of=('self',))
            .filter(
                pk__in=iscrizione_ids,
                corso=corso,
                ricevuta_iscrizione__isnull=False,
                ricevuta_iscrizione__DOTIPDOC='RF',
                ricevuta_iscrizione__lezioni_fatturate__isnull=True,
            )
            .select_related('ricevuta_iscrizione', 'alunno')
        )
        if len(iscrizioni) != len(iscrizione_ids):
            messages.error(
                request,
                'Una o più ricevute selezionate non appartengono alle '
                'iscrizioni visualizzate o sono collegate a lezioni.',
            )
            return redirect_response

        documenti_ids = {
            iscrizione.ricevuta_iscrizione_id for iscrizione in iscrizioni
        }
        iscrizioni_esterni = Alunno.objects.filter(
            ricevuta_iscrizione_id__in=documenti_ids,
        ).exclude(pk__in=iscrizione_ids)
        if iscrizioni_esterni.exists():
            messages.error(
                request,
                'Una o più ricevute sono collegate anche ad altre iscrizioni.',
            )
            return redirect_response

        documenti = list(
            Ord_Mast.objects.select_for_update(of=('self',)).filter(
                pk__in=documenti_ids,
                DOTIPDOC='RF',
                lezioni_fatturate__isnull=True,
            )
        )
        if len(documenti) != len(documenti_ids):
            messages.error(
                request,
                'Una o più ricevute non sono più disponibili o sono '
                'collegate a lezioni.',
            )
            return redirect_response

        for documento in documenti:
            documento.delete()

    messages.success(
        request,
        f'Eliminate {len(documenti_ids)} ricevute di iscrizione.',
    )
    return redirect_response


@login_required
@require_http_methods(['GET'])
def genera_iscrizioni(request):
    form = IscrizioniForm(request.GET or None)
    righe_iscrizioni = []
    configurazione_mancante = None
    numero_generabili = 0
    prezzo_tessera = None
    iscrizioni_eliminabili = set()
    if form.is_valid():
        corso = form.cleaned_data['corso']
        causale = form.cleaned_data['causale']
        iscrizioni = Alunno.objects.filter(corso=corso).select_related(
            'alunno',
            'corso',
            'ricevuta_iscrizione',
        ).order_by('alunno__NORAGSOC', 'pk')
        try:
            azienda = Azienda.get_azienda()
        except Azienda.DoesNotExist:
            azienda = None
            configurazione_mancante = (
                'Configurare i dati aziendali prima di generare le ricevute.'
            )
        if azienda is not None and (
            azienda.AZARTINS_id is None or azienda.AZARTTES_id is None
        ):
            configurazione_mancante = (
                'Configurare in Azienda gli articoli per iscrizione e tessera.'
            )
        elif azienda is not None:
            prezzo_tessera = azienda.AZARTTES.ARPREZZO or Decimal('0.00')

        iscrizioni = list(iscrizioni)
        iscrizioni_eliminabili = set(
            Alunno.objects.filter(
                pk__in=[iscrizione.pk for iscrizione in iscrizioni],
                ricevuta_iscrizione__DOTIPDOC='RF',
                ricevuta_iscrizione__lezioni_fatturate__isnull=True,
            ).values_list('pk', flat=True)
        )
        ricevute_ids = [
            iscrizione.ricevuta_iscrizione_id
            for iscrizione in iscrizioni
            if iscrizione.ricevuta_iscrizione_id
        ]
        scadenze_per_documento = {}
        for scadenza in Scadenze.objects.filter(
            SCCODICE_id__in=ricevute_ids
        ).order_by('SCNUMSCA', 'pk'):
            scadenze_per_documento.setdefault(
                scadenza.SCCODICE_id, []
            ).append(scadenza)
        totali_per_documento = {
            riga['DOCODICE_id']: riga['totale'] or Decimal('0.00')
            for riga in Ord_dett.objects.filter(
                DOCODICE_id__in=ricevute_ids
            ).values('DOCODICE_id').annotate(
                totale=Sum(F('DOPREZZO') * F('DOQTAUM1'))
            )
        }

        for iscrizione in iscrizioni:
            documento_id = iscrizione.ricevuta_iscrizione_id
            scadenze = scadenze_per_documento.get(documento_id, [])
            pagato = bool(scadenze) and all(
                scadenza.SCPAGATA == 'S' for scadenza in scadenze
            )
            generabile = documento_id is None and configurazione_mancante is None
            numero_generabili += generabile
            righe_iscrizioni.append({
                'iscrizione': iscrizione,
                'documento_id': documento_id,
                'eliminabile': iscrizione.pk in iscrizioni_eliminabili,
                'totale_documento': (
                    totali_per_documento.get(documento_id)
                    if documento_id
                    else (
                        iscrizione.corso.prezzo_iscrizione + prezzo_tessera
                        if prezzo_tessera is not None
                        else None
                    )
                ),
                'scadenze': scadenze,
                'scadenze_non_pagate': [
                    scadenza for scadenza in scadenze
                    if scadenza.SCPAGATA != 'S'
                ],
                'pagato': pagato,
                'generabile': generabile,
            })

    return render(
        request,
        'Corsi/iscrizioni.html',
        {
            'form': form,
            'righe_iscrizioni': righe_iscrizioni,
            'numero_generabili': numero_generabili,
            'numero_eliminabili': len(iscrizioni_eliminabili),
            'configurazione_mancante': configurazione_mancante,
            'prezzo_tessera': prezzo_tessera,
        },
    )


@login_required
@require_POST
def genera_ricevuta_iscrizione(request, alunno_corso_id):
    form = IscrizioniForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Selezionare un corso e una causale validi.')
        return redirect('corsi:iscrizioni')

    corso = form.cleaned_data['corso']
    causale = form.cleaned_data['causale']
    iscrizione = get_object_or_404(
        Alunno,
        pk=alunno_corso_id,
        corso=corso,
    )
    try:
        documento = _crea_ricevuta_iscrizione(
            iscrizione,
            causale,
            request.user,
        )
    except ValidationError as errore:
        messages.error(request, ' '.join(errore.messages))
    else:
        messages.success(
            request,
            f'Ricevuta fiscale {documento.pk} creata per {iscrizione.alunno}.',
        )

    return _redirect_iscrizioni(corso, causale)


@login_required
@require_POST
def elimina_ricevuta_iscrizione(request, alunno_corso_id):
    return _elimina_ricevute_iscrizione(
        request,
        [str(alunno_corso_id)],
    )


@login_required
@require_POST
def elimina_ricevute_iscrizione_selezionate(request):
    return _elimina_ricevute_iscrizione(
        request,
        request.POST.getlist('iscrizioni_ids'),
    )


@login_required
@require_POST
def genera_tutte_ricevute_iscrizione(request):
    form = IscrizioniForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Selezionare un corso e una causale validi.')
        return redirect('corsi:iscrizioni')

    corso = form.cleaned_data['corso']
    causale = form.cleaned_data['causale']
    iscrizioni = Alunno.objects.filter(
        corso=corso,
        ricevuta_iscrizione__isnull=True,
    ).select_related('alunno').order_by('alunno__NORAGSOC', 'pk')

    create_count = 0
    errori = []
    for iscrizione in iscrizioni.iterator():
        try:
            _crea_ricevuta_iscrizione(
                iscrizione,
                causale,
                request.user,
            )
        except ValidationError as errore:
            errori.append(f'{iscrizione.alunno}: {" ".join(errore.messages)}')
        else:
            create_count += 1

    if create_count:
        messages.success(
            request,
            f'Generate {create_count} ricevute di iscrizione.',
        )
    if errori:
        messages.warning(
            request,
            f'Non generate {len(errori)} ricevute: ' + '; '.join(errori),
        )
    elif not create_count:
        messages.info(request, 'Non ci sono ricevute di iscrizione da generare.')

    return _redirect_iscrizioni(corso, causale)


@login_required
@require_POST
def genera_ricevuta_alunno(request, alunno_id):
    form = FatturazioneForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Selezionare un periodo e una causale validi.')
        return redirect('corsi:fatturazione')

    anno = form.cleaned_data['anno']
    mese = form.cleaned_data['mese']
    causale = form.cleaned_data['causale']
    alunno_filtro = form.cleaned_data['alunno']
    corso_filtro = form.cleaned_data['corso']
    inizio_periodo = date(anno, mese, 1)
    fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
    nominativo = get_object_or_404(Nominativi, pk=alunno_id)

    try:
        documento = _crea_ricevuta_alunno(
            nominativo,
            causale,
            inizio_periodo,
            fine_periodo,
            request.user,
        )
    except ValidationError as errore:
        messages.error(request, ' '.join(errore.messages))
    else:
        messages.success(
            request,
            f'Ricevuta fiscale {documento.pk} creata per {nominativo}.',
        )

    return _redirect_fatturazione(
        anno, mese, causale, alunno_filtro, corso_filtro
    )


@login_required
@require_POST
def genera_tutte_ricevute(request):
    form = FatturazioneForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Selezionare un periodo e una causale validi.')
        return redirect('corsi:fatturazione')

    anno = form.cleaned_data['anno']
    mese = form.cleaned_data['mese']
    causale = form.cleaned_data['causale']
    alunno_filtro = form.cleaned_data['alunno']
    corso_filtro = form.cleaned_data['corso']
    inizio_periodo = date(anno, mese, 1)
    fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
    alunni_ids = _lezioni_fatturazione_periodo(
        inizio_periodo,
        fine_periodo,
        alunno=alunno_filtro,
        corso=corso_filtro,
    ).values_list('alunno__alunno_id', flat=True).distinct()

    create_count = 0
    errori = []
    alunni = Nominativi.objects.filter(pk__in=alunni_ids).order_by('NORAGSOC').iterator()
    for nominativo in alunni:
        try:
            _crea_ricevuta_alunno(
                nominativo,
                causale,
                inizio_periodo,
                fine_periodo,
                request.user,
            )
        except ValidationError as errore:
            errori.append(f'{nominativo}: {" ".join(errore.messages)}')
        else:
            create_count += 1

    if create_count:
        messages.success(
            request,
            f'Generate {create_count} ricevute fiscali.',
        )
    if errori:
        messages.warning(
            request,
            f'Non generate {len(errori)} ricevute: ' + '; '.join(errori),
        )
    elif not create_count:
        messages.info(request, 'Non ci sono ricevute da generare.')

    return _redirect_fatturazione(
        anno, mese, causale, alunno_filtro, corso_filtro
    )
