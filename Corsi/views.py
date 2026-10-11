from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Prefetch, Q, Sum
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
from documenti.models import Nominativi, Ord_Mast, Ord_dett, Scadenze, Settings
from documenti.services import finalizza_documento

from .forms import (
    AlunnoFormSet,
    CorsoForm,
    FatturazioneForm,
    PeriodoLezioniForm,
)
from .models import Alunno, Corso, Lezioni


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


class CorsoFormsetMixin:
    model = Corso
    form_class = CorsoForm
    template_name = 'Corsi/corso_form.html'
    success_url = reverse_lazy('corsi:elenco')

    def get_formset(self):
        if not hasattr(self, '_formset'):
            self._formset = AlunnoFormSet(
                data=self.request.POST if self.request.method == 'POST' else None,
                instance=getattr(self, 'object', None),
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
    for lezione in lezioni.order_by('data', 'alunno__ora_inizio'):
        ora_inizio = lezione.ora_inizio or lezione.alunno.ora_inizio
        inizio_lezione = datetime.combine(lezione.data, ora_inizio)
        fine_lezione = inizio_lezione + timedelta(
            minutes=lezione.alunno.durata_minuti
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
                    'corso': str(lezione.alunno.corso),
                    'alunno': str(lezione.alunno.alunno),
                    'note': lezione.note,
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

    lezione = get_object_or_404(Lezioni, pk=pk)
    lezione.data = data_lezione
    lezione.ora_inizio = ora_inizio
    lezione.save(update_fields=['data', 'ora_inizio'])
    return JsonResponse(
        {
            'id': lezione.pk,
            'data': lezione.data.isoformat(),
            'ora_inizio': lezione.ora_inizio.strftime('%H:%M'),
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
                    )
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
        form = PeriodoLezioniForm(request.GET)
    else:
        form_iniziale = PeriodoLezioniForm()
        form = PeriodoLezioniForm(
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
        inizio_periodo = date(anno, mese, 1)
        fine_periodo = date(anno, mese, monthrange(anno, mese)[1])
        lezioni = Lezioni.objects.filter(
            data__range=(inizio_periodo, fine_periodo)
        ).select_related(
            'alunno__corso__insegnante',
            'alunno__alunno',
        ).order_by(
            'alunno__corso__insegnante__NORAGSOC',
            'alunno__corso_id',
            'alunno__alunno__NORAGSOC',
            'data',
            'ora_inizio',
            'alunno__ora_inizio',
        )

        corsi_per_id = {}
        alunni_per_chiave = {}
        for lezione in lezioni:
            riga_alunno = lezione.alunno
            corso = riga_alunno.corso
            nominativo = riga_alunno.alunno
            durata = riga_alunno.durata_minuti
            ora_inizio = lezione.ora_inizio or riga_alunno.ora_inizio
            dettaglio_lezioni.append(
                {
                    'lezione': lezione,
                    'corso': corso,
                    'docente': corso.insegnante,
                    'alunno': nominativo,
                    'ora_inizio': ora_inizio,
                    'durata_minuti': durata,
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
            riepilogo_corso['minuti'] += durata

            chiave_alunno = (corso.pk, nominativo.pk)
            riepilogo_alunno = alunni_per_chiave.setdefault(
                chiave_alunno,
                {
                    'corso': corso,
                    'alunno': nominativo,
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
            riepilogo_alunno['ricavo'] = _importo_orario(
                riepilogo_alunno['minuti'],
                corso.prezzo,
            )
            corsi_per_id[corso.pk]['ricavo'] += riepilogo_alunno['ricavo']

        for riepilogo_corso in corsi_per_id.values():
            riepilogo_corso['costo'] = _importo_orario(
                riepilogo_corso['minuti'],
                riepilogo_corso['corso'].costo,
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
        totali = {
            'minuti_costo': sum(r['minuti'] for r in riepilogo_corsi),
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
            'minuti_assenza': sum(
                r['minuti_assenza'] for r in riepilogo_alunni
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
        )

        righe_per_alunno = {}
        for lezione in lezioni:
            alunno = lezione.alunno.alunno
            riepilogo = righe_per_alunno.setdefault(
                alunno.pk,
                {
                    'alunno': alunno,
                    'corsi_per_id': {},
                    'documenti': set(),
                    'numero_lezioni': 0,
                    'numero_lezioni_fatturate': 0,
                },
            )
            riepilogo['numero_lezioni'] += 1
            if lezione.documento_fatturazione_id:
                riepilogo['numero_lezioni_fatturate'] += 1
                riepilogo['documenti'].add(lezione.documento_fatturazione_id)

            corso = lezione.alunno.corso
            corso_riepilogo = riepilogo['corsi_per_id'].setdefault(
                corso.pk,
                {'corso': corso, 'minuti': 0},
            )
            corso_riepilogo['minuti'] += lezione.alunno.durata_minuti

        documenti_ids = {
            documento_id
            for riepilogo in righe_per_alunno.values()
            for documento_id in riepilogo['documenti']
        }
        scadenze_per_documento = {}
        for scadenza in Scadenze.objects.filter(
            SCCODICE_id__in=documenti_ids
        ).order_by('SCNUMSCA', 'pk'):
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
                importo = corso.prezzo
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
            Lezioni.objects.select_for_update().filter(
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
            corsi_per_id.setdefault(corso.pk, {'corso': corso})

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
            DOCODINT=nominativo,
            DOCODUTE=utente,
            DOTIPDOC='RF',
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
                DOPREZZO=corso.prezzo,
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
    alunni = Nominativi.objects.filter(pk__in=alunni_ids).order_by('NORAGSOC')
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
