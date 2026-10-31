from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from PaNet1Project import settings
from documenti.models import (
    Articoli,
    Azienda,
    Causdocu,
    Codiciva,
    Nominativi,
    Ord_Mast,
    Ord_dett,
    PAG_DETT,
    PAGAMENTI,
    Rivadett,
    Scadenze,
)

from .forms import AlunnoForm, CorsoForm, PeriodoLezioniForm
from .models import Alunno, Corso, Lezioni
from .views import date_lezioni_alunno


class PeriodoLezioniFormTests(SimpleTestCase):
    @patch('Corsi.forms.date')
    def test_default_period_is_next_month(self, mock_date):
        mock_date.today.return_value = date(2026, 10, 8)

        form = PeriodoLezioniForm()

        self.assertEqual(form.fields['anno'].initial, 2026)
        self.assertEqual(form.fields['mese'].initial, 11)

    @patch('Corsi.forms.date')
    def test_default_period_rolls_over_to_next_year(self, mock_date):
        mock_date.today.return_value = date(2026, 12, 8)

        form = PeriodoLezioniForm()

        self.assertEqual(form.fields['anno'].initial, 2027)
        self.assertEqual(form.fields['mese'].initial, 1)

    def test_validates_year_and_month(self):
        form = PeriodoLezioniForm({'anno': '2026', 'mese': '11'})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, {'anno': 2026, 'mese': 11})

    def test_course_form_limits_description_to_80_characters(self):
        form = CorsoForm()

        self.assertEqual(form.fields['descrizione'].max_length, 80)
        with self.assertRaises(ValidationError):
            form.fields['descrizione'].clean('x' * 81)

    def test_alunno_start_time_uses_quarter_hour_steps(self):
        widget = AlunnoForm().fields['ora_inizio'].widget

        self.assertEqual(len(widget.choices), 97)
        self.assertEqual(widget.choices[0], ('', 'Seleziona un orario'))
        self.assertEqual(widget.choices[1], ('00:00', '00:00'))
        self.assertEqual(widget.choices[-1], ('23:45', '23:45'))
        self.assertEqual(widget.format_value(time(17, 0)), ['17:00'])

    def test_alunno_start_time_renders_as_quarter_hour_select(self):
        widget = AlunnoForm().fields['ora_inizio'].widget

        rendered = str(widget.render('ora_inizio', time(17, 0)))

        self.assertIn('<select', rendered)
        self.assertIn('<option value="17:00" selected>', rendered)
        self.assertEqual(rendered.count('<option '), 97)

    def test_alunno_start_time_rejects_non_quarter_hour_values(self):
        field = AlunnoForm().fields['ora_inizio']

        self.assertEqual(field.clean('17:15'), time(17, 15))
        with self.assertRaises(ValidationError):
            field.clean('17:10')


class DateLezioniAlunnoTests(SimpleTestCase):
    def test_returns_weekdays_inside_selected_period(self):
        alunno = SimpleNamespace(giorno_settimana='lunedi')

        dates = list(
            date_lezioni_alunno(alunno, date(2026, 11, 3), date(2026, 11, 20))
        )

        self.assertEqual(
            dates,
            [date(2026, 11, 9), date(2026, 11, 16)],
        )


class CalendarioLezioniTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='calendario-test')
        self.client.force_login(self.user)
        insegnante = Nominativi.objects.create(
            NOCODICE='CAL-TEACHER',
            NORAGSOC='Insegnante',
            NOCOGNOM='Clapton',
            NOCODNOM=settings.CCATFOR,
        )
        self.alunno_nominativo = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT',
            NORAGSOC='Alunno di prova',
            NOCODNOM=settings.CCATCLI,
        )
        codice_iva = Codiciva.objects.create(
            CICODICE='CALIV',
            CIDESCRI='IVA test',
            CIPERIVA='22.00',
            slug='caliva',
        )
        self.articolo = Articoli.objects.create(
            ARCODICE='CAL-ART',
            ARDESCRI='Lezione di chitarra',
            ARCODIVA=codice_iva,
        )
        self.causale = Causdocu.objects.create(
            CDCODICE='RF001',
            CDDESCRI='Ricevuta fiscale',
            CDTIPDOC='RF',
            CDNUMAUT=1,
            CDQUALIT=0,
            slug='rf001',
        )
        self.pagamento = PAGAMENTI.objects.create(
            PACODICE='CALPG',
            PADESCRI='Pagamento test',
            slug='calpag',
        )
        PAG_DETT.objects.create(
            PACODICE=self.pagamento,
            PDNUMSCA=1,
            PDGIORNO='Data Doc.',
            PDPERCEN='100.0000',
        )
        self.corso = Corso.objects.create(
            descrizione='Chitarra',
            insegnante=insegnante,
            articolo=self.articolo,
            prezzo='100.00',
            costo='50.00',
            data_inizio=date(2026, 10, 1),
            data_fine=date(2026, 12, 31),
        )
        self.riga_alunno = Alunno.objects.create(
            corso=self.corso,
            alunno=self.alunno_nominativo,
            giorno_settimana='lunedi',
            ora_inizio='17:00',
            durata_minuti=45,
        )
        self.lezione = Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 12),
            data_ricorrenza=date(2026, 10, 12),
        )

    def test_course_string_uses_description_and_teacher_surname(self):
        self.assertEqual(str(self.corso), 'Chitarra Clapton')

    def test_updating_course_saves_its_description(self):
        self.corso.prezzo_iscrizione = Decimal('25.00')
        self.corso.save(update_fields=['prezzo_iscrizione'])
        response = self.client.post(
            reverse('corsi:modifica', args=[self.corso.pk]),
            {
                'descrizione': 'Chitarra acustica',
                'note': 'Lezione di prova\nPortare il libro',
                'insegnante': self.corso.insegnante_id,
                'articolo': self.articolo.ARCODICE,
                'durata_minuti': '60',
                'di_gruppo': 'on',
                'calcoloCosto': 'on',
                'prezzo': '100.00',
                'costo': '50.00',
                'data_inizio': '2026-10-01',
                'data_fine': '2026-12-31',
                'alunni-TOTAL_FORMS': '1',
                'alunni-INITIAL_FORMS': '1',
                'alunni-MIN_NUM_FORMS': '1',
                'alunni-MAX_NUM_FORMS': '1000',
                'alunni-0-id': str(self.riga_alunno.pk),
                'alunni-0-alunno': self.alunno_nominativo.pk,
                'alunni-0-prezzo': '55.50',
                'alunni-0-giorno_settimana': 'lunedi',
                'alunni-0-ora_inizio': '17:00',
                'alunni-0-durata_minuti': '45',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.corso.refresh_from_db()
        self.assertEqual(self.corso.descrizione, 'Chitarra acustica')
        self.assertEqual(self.corso.note, 'Lezione di prova\nPortare il libro')
        self.assertEqual(self.corso.articolo, self.articolo)
        self.assertEqual(self.corso.prezzo_iscrizione, Decimal('25.00'))
        self.riga_alunno.refresh_from_db()
        self.assertEqual(self.riga_alunno.prezzo, Decimal('55.50'))
        self.assertTrue(self.corso.di_gruppo)
        self.assertTrue(self.corso.calcoloCosto)

    def test_invalid_course_form_shows_a_toast(self):
        response = self.client.post(
            reverse('corsi:modifica', args=[self.corso.pk]),
            {
                'descrizione': 'Chitarra acustica',
                'insegnante': self.corso.insegnante_id,
                'articolo': self.articolo.ARCODICE,
                'durata_minuti': '60',
                'prezzo': '100.00',
                'costo': '50.00',
                'data_inizio': '',
                'data_fine': '',
                'alunni-TOTAL_FORMS': '1',
                'alunni-INITIAL_FORMS': '1',
                'alunni-MIN_NUM_FORMS': '1',
                'alunni-MAX_NUM_FORMS': '1000',
                'alunni-0-id': str(self.riga_alunno.pk),
                'alunni-0-alunno': self.alunno_nominativo.pk,
                'alunni-0-giorno_settimana': 'lunedi',
                'alunni-0-ora_inizio': '17:00',
                'alunni-0-durata_minuti': '45',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_invalid'])
        self.assertContains(response, 'form-invalid-toast')
        self.assertContains(response, 'Salvataggio non riuscito')

    def test_invalid_lesson_period_shows_a_toast(self):
        response = self.client.post(
            reverse('corsi:lezioni'),
            {'anno': '2026', 'mese': '13'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_invalid'])
        self.assertContains(response, 'form-invalid-toast')
        self.assertContains(response, 'Periodo non valido')

    def test_course_form_displays_saved_description(self):
        response = self.client.get(
            reverse('corsi:modifica', args=[self.corso.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['form']['descrizione'].value(),
            'Chitarra',
        )
        self.assertContains(response, 'name="note"')
        self.assertContains(response, 'name="alunni-0-prezzo"')
        self.assertContains(response, 'rows="4"')

    def test_new_student_duration_defaults_to_course_duration(self):
        self.corso.durata_minuti = 75
        self.corso.save()

        response = self.client.get(
            reverse('corsi:modifica', args=[self.corso.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['formset'].empty_form['durata_minuti'].value(),
            75,
        )

    def test_course_form_renders_saved_dates_in_html_date_format(self):
        response = self.client.get(
            reverse('corsi:modifica', args=[self.corso.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-10-01"')
        self.assertContains(response, 'value="2026-12-31"')

    def test_course_checkboxes_use_separate_labels_above_the_controls(self):
        response = self.client.get(
            reverse('corsi:modifica', args=[self.corso.pk])
        )

        self.assertContains(
            response,
            '<label class="form-label" for="id_di_gruppo">',
        )
        self.assertContains(
            response,
            '<label class="form-label" for="id_calcoloCosto">',
        )
        self.assertContains(response, 'form-check-input')

    def test_course_list_displays_saved_description_and_teacher_surname(self):
        response = self.client.get(reverse('corsi:elenco'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Chitarra Clapton')
        self.assertContains(response, 'Duplica')
        self.assertContains(response, 'Durata (minuti)')
        self.assertContains(response, 'Di gruppo')
        self.assertContains(response, 'Calcolo costo')
        self.assertContains(response, 'Orario')
        self.assertContains(response, '<td>60</td>', html=True)
        self.assertContains(response, '<td>No</td>', html=True)

    def test_duplicate_course_copies_course_and_students_only(self):
        self.corso.note = 'Note da copiare'
        self.corso.durata_minuti = 90
        self.corso.di_gruppo = True
        self.corso.calcoloCosto = True
        self.corso.save()
        self.corso.refresh_from_db()
        secondo_alunno = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Secondo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        seconda_riga_alunno = Alunno.objects.create(
            corso=self.corso,
            alunno=secondo_alunno,
            giorno_settimana='mercoledi',
            ora_inizio='18:15',
            durata_minuti=30,
        )
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-corso-originale',
        )
        self.lezione.documento_fatturazione = documento
        self.lezione.save(update_fields=['documento_fatturazione'])

        response = self.client.post(
            reverse('corsi:duplica', args=[self.corso.pk])
        )

        corso_duplicato = Corso.objects.exclude(pk=self.corso.pk).get()
        self.assertRedirects(
            response,
            reverse('corsi:modifica', args=[corso_duplicato.pk]),
        )
        for field in (
            'descrizione',
            'note',
            'durata_minuti',
            'di_gruppo',
            'calcoloCosto',
            'insegnante_id',
            'articolo_id',
            'prezzo',
            'costo',
            'data_inizio',
            'data_fine',
        ):
            self.assertEqual(
                getattr(corso_duplicato, field),
                getattr(self.corso, field),
            )

        alunni_duplicati = list(
            corso_duplicato.alunni.order_by('giorno_settimana', 'ora_inizio')
        )
        self.assertEqual(len(alunni_duplicati), 2)
        self.assertEqual(
            {
                (
                    riga.alunno_id,
                    riga.giorno_settimana,
                    riga.ora_inizio,
                    riga.durata_minuti,
                )
                for riga in alunni_duplicati
            },
            {
                (
                    self.riga_alunno.alunno_id,
                    self.riga_alunno.giorno_settimana,
                    time(17, 0),
                    self.riga_alunno.durata_minuti,
                ),
                (
                    seconda_riga_alunno.alunno_id,
                    seconda_riga_alunno.giorno_settimana,
                    time(18, 15),
                    seconda_riga_alunno.durata_minuti,
                ),
            },
        )
        self.assertEqual(self.corso.alunni.count(), 2)
        self.assertEqual(
            self.lezione.documento_fatturazione_id,
            documento.pk,
        )
        self.assertFalse(Lezioni.objects.filter(
            alunno__corso=corso_duplicato
        ).exists())
        self.assertFalse(
            Ord_Mast.objects.filter(
                lezioni_fatturate__alunno__corso=corso_duplicato
            ).exists()
        )

    def test_course_edit_orders_students_by_weekday_and_start_time(self):
        secondo_alunno = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Secondo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        terzo_alunno = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-3',
            NORAGSOC='Terzo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        alunno_stesso_orario = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-4',
            NORAGSOC='Aardvark',
            NOCODNOM=settings.CCATCLI,
        )
        riga_stesso_orario = Alunno.objects.create(
            corso=self.corso,
            alunno=alunno_stesso_orario,
            giorno_settimana='lunedi',
            ora_inizio='17:00',
            durata_minuti=45,
        )
        Alunno.objects.create(
            corso=self.corso,
            alunno=secondo_alunno,
            giorno_settimana='mercoledi',
            ora_inizio='17:00',
            durata_minuti=45,
        )
        Alunno.objects.create(
            corso=self.corso,
            alunno=terzo_alunno,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=45,
        )

        response = self.client.get(
            reverse('corsi:modifica', args=[self.corso.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                form.instance.pk
                for form in response.context['formset'].forms
                if form.instance.pk
            ],
            [
                riga_stesso_orario.pk,
                self.riga_alunno.pk,
                terzo_alunno.corsi_frequentati.get().pk,
                secondo_alunno.corsi_frequentati.get().pk,
            ],
        )

    def test_creating_course_saves_its_description(self):
        response = self.client.post(
            reverse('corsi:nuovo'),
            {
                'descrizione': 'Pianoforte',
                'note': 'Lezioni individuali',
                'durata_minuti': '75',
                'insegnante': self.corso.insegnante_id,
                'prezzo': '120.00',
                'costo': '60.00',
                'data_inizio': '2026-10-01',
                'data_fine': '2026-12-31',
                'alunni-TOTAL_FORMS': '1',
                'alunni-INITIAL_FORMS': '0',
                'alunni-MIN_NUM_FORMS': '1',
                'alunni-MAX_NUM_FORMS': '1000',
                'alunni-0-alunno': self.alunno_nominativo.pk,
                'alunni-0-giorno_settimana': 'martedi',
                'alunni-0-ora_inizio': '18:00',
                'alunni-0-durata_minuti': '75',
            },
        )

        self.assertEqual(response.status_code, 302)
        corso_creato = Corso.objects.get(descrizione='Pianoforte')
        self.assertEqual(corso_creato.insegnante_id, self.corso.insegnante_id)
        self.assertEqual(corso_creato.note, 'Lezioni individuali')
        self.assertEqual(corso_creato.durata_minuti, 75)
        self.assertFalse(corso_creato.di_gruppo)
        self.assertFalse(corso_creato.calcoloCosto)
        self.assertEqual(corso_creato.alunni.get().durata_minuti, 75)

    def test_calendar_page_renders(self):
        response = self.client.get(reverse('corsi:calendario-lezioni'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dayGridMonth')
        self.assertContains(response, 'filtro-corso')
        self.assertContains(response, 'filtro-alunno')

    def test_events_expose_the_course_resource_and_support_filters(self):
        response = self.client.get(
            reverse('corsi:calendario-eventi'),
            {
                'start': '2026-10-01T00:00:00',
                'end': '2026-11-01T00:00:00',
                'corso': self.corso.pk,
                'alunno': self.alunno_nominativo.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        evento = response.json()[0]
        self.assertEqual(evento['resourceId'], str(self.corso.pk))
        self.assertEqual(evento['start'], '2026-10-12T17:00:00')
        self.assertEqual(evento['end'], '2026-10-12T17:45:00')
        self.assertEqual(evento['extendedProps']['corso'], str(self.corso))

        response = self.client.get(
            reverse('corsi:calendario-eventi'),
            {
                'start': '2026-10-01',
                'end': '2026-11-01',
                'corso': self.corso.pk + 1,
            },
        )
        self.assertEqual(response.json(), [])

    def test_event_override_changes_only_the_selected_lesson(self):
        response = self.client.post(
            reverse(
                'corsi:modifica-orario-lezione',
                args=[self.lezione.pk],
            ),
            {'data': '2026-10-14', 'ora_inizio': '18:30'},
        )

        self.assertEqual(response.status_code, 200)
        self.lezione.refresh_from_db()
        self.riga_alunno.refresh_from_db()
        self.assertEqual(self.lezione.data, date(2026, 10, 14))
        self.assertEqual(self.lezione.data_ricorrenza, date(2026, 10, 12))
        self.assertEqual(str(self.lezione.ora_inizio), '18:30:00')
        self.assertEqual(str(self.riga_alunno.ora_inizio), '17:00:00')

        response = self.client.get(
            reverse('corsi:calendario-eventi'),
            {'start': '2026-10-01', 'end': '2026-11-01'},
        )
        evento = response.json()[0]
        self.assertEqual(evento['start'], '2026-10-14T18:30:00')

    def test_event_duration_can_be_changed_without_changing_the_schedule(self):
        response = self.client.post(
            reverse(
                'corsi:modifica-orario-lezione',
                args=[self.lezione.pk],
            ),
            {
                'data': '2026-10-12',
                'ora_inizio': '17:00',
                'durata_minuti': '60',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['durata_minuti'], 60)
        self.lezione.refresh_from_db()
        self.riga_alunno.refresh_from_db()
        self.assertEqual(self.lezione.durata_minuti, 60)
        self.assertEqual(self.riga_alunno.durata_minuti, 45)

        response = self.client.get(
            reverse('corsi:calendario-eventi'),
            {'start': '2026-10-01', 'end': '2026-11-01'},
        )
        evento = response.json()[0]
        self.assertEqual(evento['end'], '2026-10-12T18:00:00')
        self.assertEqual(evento['extendedProps']['durata_minuti'], 60)

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )
        self.assertEqual(
            response.context['dettaglio_lezioni'][0]['durata_minuti'],
            60,
        )

    def test_invalid_event_duration_is_rejected(self):
        response = self.client.post(
            reverse(
                'corsi:modifica-orario-lezione',
                args=[self.lezione.pk],
            ),
            {
                'data': '2026-10-12',
                'ora_inizio': '17:00',
                'durata_minuti': '0',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.lezione.refresh_from_db()
        self.assertIsNone(self.lezione.durata_minuti)

    def test_teacher_role_only_allows_calendar_actions(self):
        self.user.groups.add(Group.objects.get(name='Insegnante'))

        response = self.client.get(reverse('home'))
        self.assertRedirects(
            response,
            reverse('corsi:calendario-lezioni'),
        )

        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(
            response,
            reverse('corsi:calendario-lezioni'),
        )
        self.assertRedirects(
            self.client.get(reverse('login')),
            reverse('corsi:calendario-lezioni'),
        )

        calendar_response = self.client.get(
            reverse('corsi:calendario-lezioni')
        )
        self.assertEqual(calendar_response.status_code, 200)
        self.assertTrue(calendar_response.context['is_insegnante'])
        visible_menu = calendar_response.context['MENU_TREE']
        self.assertEqual(
            [item.label for item in visible_menu],
            ['Corsi', 'Servizi'],
        )
        self.assertEqual(
            [item.label for item in visible_menu[0].child_list],
            ['Calendario lezioni'],
        )
        self.assertEqual(
            [item.label for item in visible_menu[1].child_list],
            ['Logout'],
        )

        allowed_event_response = self.client.get(
            reverse('corsi:calendario-eventi'),
            {'start': '2026-10-01', 'end': '2026-11-01'},
        )
        self.assertEqual(allowed_event_response.status_code, 200)
        allowed_presence_response = self.client.post(
            reverse('corsi:aggiorna-presenza', args=[self.lezione.pk]),
            {'presenza': 'true'},
        )
        self.assertEqual(allowed_presence_response.status_code, 200)
        allowed_move_response = self.client.post(
            reverse(
                'corsi:modifica-orario-lezione',
                args=[self.lezione.pk],
            ),
            {'data': '2026-10-14', 'ora_inizio': '18:30'},
        )
        self.assertEqual(allowed_move_response.status_code, 200)

        for url in (
            reverse('corsi:elenco'),
            reverse('corsi:lezioni'),
            reverse('corsi:presenze-mensili'),
            reverse('corsi:fatturazione'),
            reverse('clienti'),
            reverse('admin:index'),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        self.assertEqual(
            self.client.post(reverse('corsi:lezioni')).status_code,
            403,
        )

    def test_generating_lessons_again_does_not_duplicate_a_moved_lesson(self):
        self.client.post(
            reverse(
                'corsi:modifica-orario-lezione',
                args=[self.lezione.pk],
            ),
            {'data': '2026-10-14', 'ora_inizio': '18:30'},
        )

        response = self.client.post(
            reverse('corsi:lezioni'),
            {
                'anno': '2026',
                'mese': '10',
                'corso_singolo': str(self.corso.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        lezioni_ottobre = Lezioni.objects.filter(
            alunno=self.riga_alunno,
            data_ricorrenza__range=(date(2026, 10, 1), date(2026, 10, 31)),
        )
        self.assertEqual(lezioni_ottobre.count(), 4)
        self.assertEqual(
            lezioni_ottobre.filter(data_ricorrenza=date(2026, 10, 12)).count(),
            1,
        )

    def test_deleting_course_lessons_keeps_attended_and_invoiced_lessons(self):
        lezione_con_presenza = Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 19),
            data_ricorrenza=date(2026, 10, 19),
            presenza=True,
        )
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 20),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-lezione-protetta',
        )
        lezione_fatturata = Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 26),
            data_ricorrenza=date(2026, 10, 26),
            documento_fatturazione=documento,
        )
        lezione_mese_successivo = Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 11, 2),
            data_ricorrenza=date(2026, 11, 2),
        )

        response = self.client.post(
            reverse('corsi:lezioni'),
            {
                'anno': '2026',
                'mese': '10',
                'elimina_corso': str(self.corso.pk),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lezioni.objects.filter(pk=self.lezione.pk).exists())
        self.assertTrue(
            Lezioni.objects.filter(pk=lezione_con_presenza.pk).exists()
        )
        self.assertTrue(
            Lezioni.objects.filter(pk=lezione_fatturata.pk).exists()
        )
        self.assertTrue(
            Lezioni.objects.filter(pk=lezione_mese_successivo.pk).exists()
        )
        self.assertContains(response, 'Lezioni eliminate: 1')
        self.assertContains(response, '2 lezioni sono state mantenute')

    def test_deleting_lessons_rejects_course_outside_selected_month(self):
        altro_corso = Corso.objects.create(
            descrizione='Altro corso',
            insegnante=self.corso.insegnante,
            prezzo='100.00',
            costo='50.00',
            data_inizio=date(2026, 11, 1),
            data_fine=date(2026, 12, 31),
        )

        response = self.client.post(
            reverse('corsi:lezioni'),
            {
                'anno': '2026',
                'mese': '10',
                'elimina_corso': str(altro_corso.pk),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Lezioni.objects.filter(pk=self.lezione.pk).exists())
        self.assertContains(
            response,
            'Il corso selezionato non appartiene al periodo indicato.',
        )

    def test_invalid_event_date_or_time_is_rejected(self):
        response = self.client.post(
            reverse(
                'corsi:modifica-orario-lezione',
                args=[self.lezione.pk],
            ),
            {'data': 'non-una-data', 'ora_inizio': 'not-a-time'},
        )

        self.assertEqual(response.status_code, 400)
        self.lezione.refresh_from_db()
        self.assertEqual(self.lezione.data, date(2026, 10, 12))
        self.assertIsNone(self.lezione.ora_inizio)

    def test_attendance_is_updated_from_a_single_post(self):
        response = self.client.post(
            reverse('corsi:aggiorna-presenza', args=[self.lezione.pk]),
            {'presenza': 'true'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['presenza'])
        self.lezione.refresh_from_db()
        self.assertTrue(self.lezione.presenza)

    def test_invalid_attendance_value_is_rejected(self):
        response = self.client.post(
            reverse('corsi:aggiorna-presenza', args=[self.lezione.pk]),
            {'presenza': 'yes'},
        )

        self.assertEqual(response.status_code, 400)
        self.lezione.refresh_from_db()
        self.assertFalse(self.lezione.presenza)

    def test_monthly_attendance_report_includes_attended_and_absent_lessons(self):
        Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 19),
            data_ricorrenza=date(2026, 10, 19),
            presenza=True,
        )

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['dettaglio_lezioni']), 2)
        self.assertEqual(
            response.context['dettaglio_lezioni'][0]['ore'],
            Decimal('0.75'),
        )
        riepilogo_alunno = response.context['riepilogo_alunni'][0]
        self.assertEqual(riepilogo_alunno['minuti'], 90)
        self.assertEqual(riepilogo_alunno['ore'], Decimal('1.5'))
        self.assertEqual(riepilogo_alunno['minuti_assenza'], 45)
        self.assertEqual(riepilogo_alunno['ore_assenza'], Decimal('0.75'))
        self.assertEqual(riepilogo_alunno['ricavo'], Decimal('75.00'))

        riepilogo_corso = response.context['riepilogo_corsi'][0]
        self.assertEqual(riepilogo_corso['minuti'], 90)
        self.assertEqual(riepilogo_corso['ore'], Decimal('1.5'))
        self.assertEqual(riepilogo_corso['costo'], Decimal('75.00'))
        self.assertEqual(riepilogo_corso['ricavo'], Decimal('75.00'))
        self.assertEqual(riepilogo_corso['differenza'], Decimal('0.00'))

        totali = response.context['totali']
        self.assertEqual(totali['minuti_alunni'], 90)
        self.assertEqual(totali['ore_alunni'], Decimal('1.5'))
        self.assertEqual(totali['minuti_assenza'], 45)
        self.assertEqual(totali['ore_assenza'], Decimal('0.75'))
        self.assertEqual(totali['costo'], Decimal('75.00'))
        self.assertEqual(totali['ricavo'], Decimal('75.00'))
        self.assertEqual(totali['differenza'], Decimal('0.00'))

    def test_monthly_attendance_report_formats_large_numbers_with_thousands_separator(self):
        self.lezione.durata_minuti = 12345
        self.lezione.save(update_fields=['durata_minuti'])

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345')
        self.assertContains(response, '10.287,50')

    def test_monthly_attendance_report_displays_negative_values_in_red(self):
        self.corso.costo = Decimal('200.00')
        self.corso.save(update_fields=['costo'])

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<td class="text-danger">-75,00</td>',
            html=True,
        )

    def test_monthly_revenue_uses_student_duration_relative_to_course_default(self):
        self.corso.durata_minuti = 120
        self.corso.save()
        self.lezione.durata_minuti = 90
        self.lezione.save(update_fields=['durata_minuti'])

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['riepilogo_alunni'][0]['minuti'],
            90,
        )
        self.assertEqual(
            response.context['riepilogo_alunni'][0]['ricavo'],
            Decimal('37.50'),
        )
        self.assertEqual(
            response.context['riepilogo_corsi'][0]['ricavo'],
            Decimal('37.50'),
        )

    def test_monthly_revenue_does_not_scale_with_number_of_lessons(self):
        Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 19),
            data_ricorrenza=date(2026, 10, 19),
            durata_minuti=90,
        )

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        riepilogo_alunno = response.context['riepilogo_alunni'][0]
        self.assertEqual(riepilogo_alunno['minuti'], 135)
        self.assertEqual(riepilogo_alunno['ricavo'], Decimal('75.00'))

    def test_monthly_course_cost_counts_shared_time_slot_once(self):
        altro_alunno_nominativo = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Secondo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        altro_riga_alunno = Alunno.objects.create(
            corso=self.corso,
            alunno=altro_alunno_nominativo,
            giorno_settimana='lunedi',
            ora_inizio='17:00',
            durata_minuti=45,
        )
        Lezioni.objects.create(
            alunno=altro_riga_alunno,
            data=date(2026, 10, 12),
            data_ricorrenza=date(2026, 10, 12),
        )

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        riepilogo_corso = response.context['riepilogo_corsi'][0]
        self.assertEqual(riepilogo_corso['minuti'], 90)
        self.assertEqual(riepilogo_corso['costo'], Decimal('75.00'))
        self.assertEqual(response.context['totali']['minuti_costo'], 90)
        self.assertEqual(response.context['totali']['minuti_alunni'], 90)
        self.assertEqual(len(response.context['riepilogo_alunni']), 2)

        self.corso.di_gruppo = True
        self.corso.save()
        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        riepilogo_corso = response.context['riepilogo_corsi'][0]
        self.assertEqual(riepilogo_corso['minuti'], 45)
        self.assertEqual(riepilogo_corso['costo'], Decimal('37.50'))

        altro_riga_alunno.durata_minuti = 30
        altro_riga_alunno.save()
        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        riepilogo_corso = response.context['riepilogo_corsi'][0]
        self.assertEqual(riepilogo_corso['minuti'], 75)
        self.assertEqual(riepilogo_corso['costo'], Decimal('62.50'))

    def test_monthly_forfait_course_cost_does_not_depend_on_lesson_minutes(self):
        self.corso.calcoloCosto = True
        self.corso.save(update_fields=['calcoloCosto'])
        Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 19),
            data_ricorrenza=date(2026, 10, 19),
            durata_minuti=90,
        )

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2026', 'mese': '10'},
        )

        self.assertEqual(response.status_code, 200)
        riepilogo_corso = response.context['riepilogo_corsi'][0]
        self.assertEqual(riepilogo_corso['minuti'], 135)
        self.assertEqual(riepilogo_corso['costo'], Decimal('50.00'))
        self.assertEqual(response.context['totali']['costo'], Decimal('50.00'))

    def test_billing_counts_each_course_price_once_per_student(self):
        Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 19),
            data_ricorrenza=date(2026, 10, 19),
            presenza=True,
        )
        secondo_articolo = Articoli.objects.create(
            ARCODICE='CAL-ART2',
            ARDESCRI='Lezione di teoria',
            ARCODIVA=self.articolo.ARCODIVA,
        )
        secondo_corso = Corso.objects.create(
            descrizione='Teoria',
            insegnante=self.corso.insegnante,
            articolo=secondo_articolo,
            prezzo='60.00',
            costo='25.00',
            data_inizio=date(2026, 10, 1),
            data_fine=date(2026, 12, 31),
        )
        seconda_riga_alunno = Alunno.objects.create(
            corso=secondo_corso,
            alunno=self.alunno_nominativo,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=30,
        )
        Lezioni.objects.create(
            alunno=seconda_riga_alunno,
            data=date(2026, 10, 13),
            data_ricorrenza=date(2026, 10, 13),
            presenza=True,
        )
        altro_alunno = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Altro alunno',
            NOCODNOM=settings.CCATCLI,
        )
        altra_riga_alunno = Alunno.objects.create(
            corso=self.corso,
            alunno=altro_alunno,
            giorno_settimana='mercoledi',
            ora_inizio='19:00',
            durata_minuti=30,
        )
        Lezioni.objects.create(
            alunno=altra_riga_alunno,
            data=date(2026, 10, 14),
            data_ricorrenza=date(2026, 10, 14),
        )

        response = self.client.get(
            reverse('corsi:fatturazione'),
            {
                'anno': '2026',
                'mese': '10',
                'causale': self.causale.pk,
                'corso': secondo_corso.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['righe_fatturazione']), 1)
        riepilogo = response.context['righe_fatturazione'][0]
        self.assertEqual(len(riepilogo['corsi']), 2)
        self.assertEqual(riepilogo['totale'], Decimal('105.00'))
        self.assertEqual(
            [voce['importo'] for voce in riepilogo['corsi']],
            [Decimal('75.00'), Decimal('30.00')],
        )
        self.assertEqual(
            response.context['totale_corsi_da_pagare'],
            Decimal('105.00'),
        )
        self.assertTrue(riepilogo['generabile'])
        self.assertContains(response, 'Genera ricevuta')

    def test_billing_student_filter_only_shows_selected_student(self):
        altro_alunno = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Altro alunno',
            NOCODNOM=settings.CCATCLI,
        )
        altra_riga_alunno = Alunno.objects.create(
            corso=self.corso,
            alunno=altro_alunno,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=30,
        )
        Lezioni.objects.create(
            alunno=altra_riga_alunno,
            data=date(2026, 10, 13),
            data_ricorrenza=date(2026, 10, 13),
        )

        response = self.client.get(
            reverse('corsi:fatturazione'),
            {
                'anno': '2026',
                'mese': '10',
                'causale': self.causale.pk,
                'alunno': self.alunno_nominativo.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        righe = response.context['righe_fatturazione']
        self.assertEqual(len(righe), 1)
        self.assertEqual(righe[0]['alunno'], self.alunno_nominativo)

    @patch('Corsi.views.Settings.get_settings')
    def test_billing_uses_student_price_in_preview_and_receipt(self, get_settings):
        get_settings.return_value = SimpleNamespace(AZPAGDEF=self.pagamento)
        self.riga_alunno.prezzo = Decimal('42.75')
        self.riga_alunno.save(update_fields=['prezzo'])
        dati_fatturazione = {
            'anno': '2026',
            'mese': '10',
            'causale': self.causale.pk,
        }

        response = self.client.get(
            reverse('corsi:fatturazione'),
            dati_fatturazione,
        )

        self.assertEqual(response.status_code, 200)
        riepilogo = response.context['righe_fatturazione'][0]
        self.assertEqual(riepilogo['totale'], Decimal('42.75'))
        self.assertEqual(riepilogo['corsi'][0]['importo'], Decimal('42.75'))

        response = self.client.post(
            reverse(
                'corsi:genera-ricevuta',
                args=[self.alunno_nominativo.pk],
            ),
            dati_fatturazione,
        )

        self.assertEqual(response.status_code, 302)
        documento = Ord_Mast.objects.get(DOCODCAU=self.causale)
        riga_ricevuta = Ord_dett.objects.get(DOCODICE=documento)
        self.assertEqual(riga_ricevuta.DOPREZZO, Decimal('42.75'))

    def test_billing_can_delete_receipt_and_unlink_its_lessons(self):
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-da-eliminare',
        )
        self.lezione.documento_fatturazione = documento
        self.lezione.save(update_fields=['documento_fatturazione'])
        Ord_dett.objects.create(
            DOCODICE=documento,
            DONUMRIG=1,
            DOCODART=self.articolo,
            DOQTAUM1='1',
            DOPREZZO='100.00',
        )

        response = self.client.post(
            reverse('corsi:elimina-ricevuta', args=[documento.pk]),
            {'anno': '2026', 'mese': '10', 'causale': self.causale.pk},
        )

        self.assertRedirects(
            response,
            reverse('corsi:fatturazione')
            + f'?anno=2026&mese=10&causale={self.causale.pk}',
        )
        self.assertFalse(Ord_Mast.objects.filter(pk=documento.pk).exists())
        self.assertFalse(Ord_dett.objects.filter(DOCODICE=documento).exists())
        self.lezione.refresh_from_db()
        self.assertIsNone(self.lezione.documento_fatturazione_id)

    def test_billing_can_bulk_delete_selected_receipts_only(self):
        altro_nominativo = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Secondo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        altra_riga = Alunno.objects.create(
            corso=self.corso,
            alunno=altro_nominativo,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=45,
        )
        altra_lezione = Lezioni.objects.create(
            alunno=altra_riga,
            data=date(2026, 10, 13),
            data_ricorrenza=date(2026, 10, 13),
        )
        documenti = []
        for indice, (nominativo, lezione) in enumerate(
            (
                (self.alunno_nominativo, self.lezione),
                (altro_nominativo, altra_lezione),
            ),
            start=1,
        ):
            documento = Ord_Mast.objects.create(
                DODATORD=date(2026, 10, 10),
                DOCODCAU=self.causale,
                DOCODINT=nominativo,
                DOCODUTE=self.user,
                DOTIPDOC='RF',
                slug=f'ricevuta-multipla-{indice}',
            )
            lezione.documento_fatturazione = documento
            lezione.save(update_fields=['documento_fatturazione'])
            documenti.append(documento)
        altra_ricevuta = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-non-collegata',
        )

        response = self.client.get(
            reverse('corsi:fatturazione'),
            {'anno': '2026', 'mese': '10', 'causale': self.causale.pk},
        )

        self.assertContains(response, 'elimina-ricevute-form')
        self.assertContains(response, 'Seleziona tutte le ricevute')
        response = self.client.post(
            reverse('corsi:elimina-ricevute-selezionate'),
            {
                'anno': '2026',
                'mese': '10',
                'causale': self.causale.pk,
                'documenti_ids': [
                    str(documento.pk)
                    for documento in (*documenti, altra_ricevuta)
                ],
            },
        )

        self.assertEqual(
            Ord_Mast.objects.filter(
                pk__in=[
                    documento.pk
                    for documento in (*documenti, altra_ricevuta)
                ]
            ).count(),
            3,
        )
        response = self.client.post(
            reverse('corsi:elimina-ricevute-selezionate'),
            {
                'anno': '2026',
                'mese': '10',
                'causale': self.causale.pk,
                'documenti_ids': [str(documento.pk) for documento in documenti],
            },
        )

        self.assertRedirects(
            response,
            reverse('corsi:fatturazione')
            + f'?anno=2026&mese=10&causale={self.causale.pk}',
        )
        self.assertFalse(
            Ord_Mast.objects.filter(
                pk__in=[documento.pk for documento in documenti]
            ).exists()
        )
        self.assertTrue(
            Ord_Mast.objects.filter(pk=altra_ricevuta.pk).exists()
        )
        self.lezione.refresh_from_db()
        altra_lezione.refresh_from_db()
        self.assertIsNone(self.lezione.documento_fatturazione_id)
        self.assertIsNone(altra_lezione.documento_fatturazione_id)

    @patch('Corsi.views.Settings.get_settings')
    def test_billing_creates_receipt_lines_and_links_all_month_lessons(
        self,
        get_settings,
    ):
        get_settings.return_value = SimpleNamespace(AZPAGDEF=self.pagamento)
        Lezioni.objects.create(
            alunno=self.riga_alunno,
            data=date(2026, 10, 19),
            data_ricorrenza=date(2026, 10, 19),
            presenza=True,
        )
        secondo_articolo = Articoli.objects.create(
            ARCODICE='CAL-ART2',
            ARDESCRI='Lezione di teoria',
            ARCODIVA=self.articolo.ARCODIVA,
        )
        secondo_corso = Corso.objects.create(
            descrizione='Teoria',
            insegnante=self.corso.insegnante,
            articolo=secondo_articolo,
            prezzo='60.00',
            costo='25.00',
            data_inizio=date(2026, 10, 1),
            data_fine=date(2026, 12, 31),
        )
        seconda_riga_alunno = Alunno.objects.create(
            corso=secondo_corso,
            alunno=self.alunno_nominativo,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=30,
        )
        Lezioni.objects.create(
            alunno=seconda_riga_alunno,
            data=date(2026, 10, 13),
            data_ricorrenza=date(2026, 10, 13),
            presenza=False,
        )
        dati_fatturazione = {
            'anno': '2026',
            'mese': '10',
            'causale': self.causale.pk,
        }

        response = self.client.post(
            reverse(
                'corsi:genera-ricevuta',
                args=[self.alunno_nominativo.pk],
            ),
            dati_fatturazione,
        )

        self.assertEqual(response.status_code, 302)
        documento = Ord_Mast.objects.get(DOCODCAU=self.causale)
        response = self.client.get(
            reverse('corsi:fatturazione'),
            dati_fatturazione,
        )
        self.assertEqual(
            response.context['righe_fatturazione'][0]['totale'],
            Decimal('105.00'),
        )
        self.assertContains(response, 'Apri ricevuta')
        self.assertContains(
            response,
            reverse(
                'edit_ordine',
                kwargs={
                    'order_id': documento.pk,
                    'TipoDocumentoSelezionato': 'RF',
                },
            ),
        )
        self.assertContains(
            response,
            reverse('stampaDocumento', kwargs={'pk': documento.pk}),
        )
        self.assertEqual(documento.DOCODINT, self.alunno_nominativo)
        self.assertEqual(documento.DOCODPAG, self.pagamento)
        righe_documento = list(
            Ord_dett.objects.filter(DOCODICE=documento).order_by('DONUMRIG')
        )
        self.assertEqual(len(righe_documento), 2)
        self.assertEqual(righe_documento[0].DOCODART, self.articolo)
        self.assertEqual(righe_documento[0].DOQTAUM1, Decimal('1'))
        self.assertEqual(righe_documento[0].DOPREZZO, Decimal('75.00'))
        self.assertEqual(righe_documento[1].DOCODART, secondo_articolo)
        self.assertEqual(righe_documento[1].DOPREZZO, Decimal('30.00'))
        castelletto_iva = Rivadett.objects.get(RICODICE=documento)
        self.assertEqual(castelletto_iva.RICODIVA, self.articolo.ARCODIVA)
        self.assertEqual(castelletto_iva.RIIMPONI, Decimal('105.00'))
        self.assertEqual(castelletto_iva.RIIMPOST, Decimal('23.10'))
        scadenza = Scadenze.objects.get(SCCODICE=documento)
        self.assertEqual(scadenza.SCIMPSCA, Decimal('128.00'))
        self.assertEqual(
            Lezioni.objects.filter(
                alunno__alunno=self.alunno_nominativo,
                data__month=10,
                data__year=2026,
                documento_fatturazione=documento,
            ).count(),
            3,
        )

        response = self.client.post(
            reverse(
                'corsi:genera-ricevuta',
                args=[self.alunno_nominativo.pk],
            ),
            dati_fatturazione,
            follow=True,
        )

        self.assertEqual(Ord_Mast.objects.filter(DOCODCAU=self.causale).count(), 1)
        self.assertContains(response, 'già collegate a una ricevuta')

    @patch('Corsi.views.Settings.get_settings')
    def test_bulk_billing_generates_receipts_for_unbilled_students_only(
        self,
        get_settings,
    ):
        get_settings.return_value = SimpleNamespace(AZPAGDEF=self.pagamento)
        secondo_alunno = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-2',
            NORAGSOC='Secondo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        seconda_riga_alunno = Alunno.objects.create(
            corso=self.corso,
            alunno=secondo_alunno,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=45,
        )
        seconda_lezione = Lezioni.objects.create(
            alunno=seconda_riga_alunno,
            data=date(2026, 10, 13),
            data_ricorrenza=date(2026, 10, 13),
            presenza=False,
        )
        dati_fatturazione = {
            'anno': '2026',
            'mese': '10',
            'causale': self.causale.pk,
        }

        response = self.client.get(
            reverse('corsi:fatturazione'),
            dati_fatturazione,
        )
        self.assertContains(response, 'Genera tutte le ricevute non ancora create')
        self.assertEqual(response.context['numero_ricevute_generabili'], 2)

        response = self.client.post(
            reverse('corsi:genera-tutte-ricevute'),
            dati_fatturazione,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Ord_Mast.objects.filter(DOCODCAU=self.causale).count(),
            2,
        )
        self.lezione.refresh_from_db()
        seconda_lezione.refresh_from_db()
        self.assertIsNotNone(self.lezione.documento_fatturazione_id)
        self.assertIsNotNone(seconda_lezione.documento_fatturazione_id)
        self.assertNotEqual(
            self.lezione.documento_fatturazione_id,
            seconda_lezione.documento_fatturazione_id,
        )
        self.assertContains(response, 'Generate 2 ricevute fiscali')

        self.client.post(
            reverse('corsi:genera-tutte-ricevute'),
            dati_fatturazione,
        )
        self.assertEqual(
            Ord_Mast.objects.filter(DOCODCAU=self.causale).count(),
            2,
        )

    def test_billing_refuses_courses_without_an_article(self):
        self.corso.articolo = None
        self.corso.save(update_fields=['articolo'])
        response = self.client.get(
            reverse('corsi:fatturazione'),
            {
                'anno': '2026',
                'mese': '10',
                'causale': self.causale.pk,
            },
        )

        self.assertFalse(response.context['righe_fatturazione'][0]['generabile'])
        self.assertContains(response, 'Articolo mancante')

    def test_billing_shows_paid_only_when_all_receipt_due_dates_are_paid(self):
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-test-saldo',
        )
        self.lezione.documento_fatturazione = documento
        self.lezione.save(update_fields=['documento_fatturazione'])
        Ord_dett.objects.create(
            DOCODICE=documento,
            DONUMRIG=1,
            DOCODART=self.articolo,
            DOQTAUM1='1',
            DOPREZZO='100.00',
        )
        prima_scadenza = Scadenze.objects.create(
            SCCODICE=documento,
            SCNUMSCA=1,
            SCIMPSCA='50.00',
            SCPAGATA='N',
        )
        seconda_scadenza = Scadenze.objects.create(
            SCCODICE=documento,
            SCNUMSCA=2,
            SCIMPSCA='50.00',
            SCPAGATA='N',
        )
        parametri = {
            'anno': '2026',
            'mese': '10',
            'causale': self.causale.pk,
        }
        url_fatturazione = reverse('corsi:fatturazione')
        response = self.client.get(url_fatturazione, parametri)

        self.assertFalse(response.context['righe_fatturazione'][0]['pagato'])
        self.assertEqual(
            response.context['righe_fatturazione'][0]['totale_documento'],
            Decimal('100.00'),
        )
        self.assertEqual(
            response.context['totale_documenti_pagati'],
            Decimal('0.00'),
        )
        self.assertEqual(
            response.context['totale_documenti_non_pagati'],
            Decimal('100.00'),
        )
        self.assertEqual(
            len(response.context['righe_fatturazione'][0]['scadenze_non_pagate']),
            2,
        )
        self.assertContains(response, 'Salda #1')
        self.assertContains(response, 'Salda #2')

        referer = f'{url_fatturazione}?anno=2026&mese=10&causale={self.causale.pk}'
        response = self.client.post(
            reverse('salda_scadenza', args=[prima_scadenza.pk]),
            HTTP_REFERER=referer,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['righe_fatturazione'][0]['pagato'])
        seconda_scadenza.refresh_from_db()
        self.assertEqual(seconda_scadenza.SCPAGATA, 'N')

        response = self.client.post(
            reverse('salda_scadenza', args=[seconda_scadenza.pk]),
            HTTP_REFERER=referer,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['righe_fatturazione'][0]['pagato'])
        self.assertEqual(
            response.context['totale_documenti_pagati'],
            Decimal('100.00'),
        )
        self.assertEqual(
            response.context['totale_documenti_non_pagati'],
            Decimal('0.00'),
        )
        self.assertContains(response, 'Pagato')

    def test_billing_settles_due_dates_without_reloading_the_page(self):
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-test-saldo-ajax',
        )
        self.lezione.documento_fatturazione = documento
        self.lezione.save(update_fields=['documento_fatturazione'])
        Ord_dett.objects.create(
            DOCODICE=documento,
            DONUMRIG=1,
            DOCODART=self.articolo,
            DOQTAUM1='1',
            DOPREZZO='100.00',
        )
        prima_scadenza = Scadenze.objects.create(
            SCCODICE=documento,
            SCNUMSCA=1,
            SCIMPSCA='50.00',
            SCPAGATA='N',
        )
        seconda_scadenza = Scadenze.objects.create(
            SCCODICE=documento,
            SCNUMSCA=2,
            SCIMPSCA='50.00',
            SCPAGATA='N',
        )
        response = self.client.get(
            reverse('corsi:fatturazione'),
            {'anno': '2026', 'mese': '10', 'causale': self.causale.pk},
        )
        self.assertContains(response, 'js-salda-scadenza')
        self.assertContains(response, 'totale-documenti-pagati')

        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        response = self.client.post(
            reverse('salda_scadenza', args=[prima_scadenza.pk]),
            **headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'documento_pagato': False,
        })
        self.assertEqual(
            Scadenze.objects.get(pk=prima_scadenza.pk).SCPAGATA,
            'S',
        )
        self.assertEqual(
            Scadenze.objects.get(pk=seconda_scadenza.pk).SCPAGATA,
            'N',
        )

        response = self.client.post(
            reverse('salda_scadenza', args=[seconda_scadenza.pk]),
            **headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'documento_pagato': True,
        })

    def test_deleting_receipt_clears_its_lesson_reference(self):
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-test-cancellazione',
        )
        self.lezione.documento_fatturazione = documento
        self.lezione.save(update_fields=['documento_fatturazione'])

        documento.delete()

        self.lezione.refresh_from_db()
        self.assertIsNone(self.lezione.documento_fatturazione_id)
        self.assertTrue(Lezioni.objects.filter(pk=self.lezione.pk).exists())

    def test_enrollment_receipt_contains_registration_and_card_lines(self):
        articolo_iscrizione = Articoli.objects.create(
            ARCODICE='CAL-INS',
            ARDESCRI='Quota iscrizione',
            ARCODIVA=self.articolo.ARCODIVA,
            ARPREZZO='0.00',
        )
        articolo_tessera = Articoli.objects.create(
            ARCODICE='CAL-TES',
            ARDESCRI='Tessera associativa',
            ARCODIVA=self.articolo.ARCODIVA,
            ARPREZZO='12.50',
        )
        azienda = Azienda.objects.order_by('NOME').first()
        if azienda is None:
            azienda = Azienda.objects.create(NOME='Scuola test')
        azienda.AZARTINS = articolo_iscrizione
        azienda.AZARTTES = articolo_tessera
        azienda.save(update_fields=['AZARTINS', 'AZARTTES'])
        self.corso.prezzo_iscrizione = Decimal('25.00')
        self.corso.save(update_fields=['prezzo_iscrizione'])
        self.causale.CDPAGDEF = self.pagamento
        self.causale.save(update_fields=['CDPAGDEF'])

        filtri = {
            'corso': str(self.corso.pk),
            'causale': self.causale.pk,
        }
        response = self.client.get(reverse('corsi:iscrizioni'), filtri)
        self.assertEqual(
            response.context['numero_generabili'],
            1,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Genera tutte le ricevute mancanti')

        response = self.client.post(
            reverse('corsi:genera-tutte-ricevute-iscrizione'),
            filtri,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.riga_alunno.refresh_from_db()
        documento = self.riga_alunno.ricevuta_iscrizione
        self.assertIsNotNone(documento)
        righe = list(
            Ord_dett.objects.filter(DOCODICE=documento).order_by('DONUMRIG')
        )
        self.assertEqual(len(righe), 2)
        self.assertEqual(righe[0].DOCODART, articolo_iscrizione)
        self.assertEqual(righe[0].DOPREZZO, Decimal('25.00'))
        self.assertEqual(righe[1].DOCODART, articolo_tessera)
        self.assertEqual(righe[1].DOPREZZO, Decimal('12.50'))
        self.assertEqual(
            Scadenze.objects.get(SCCODICE=documento).SCIMPSCA,
            Decimal('45.75'),
        )
        self.assertContains(response, 'Apri ricevuta')
        self.assertContains(
            response,
            reverse(
                'edit_ordine',
                kwargs={
                    'order_id': documento.pk,
                    'TipoDocumentoSelezionato': 'RF',
                },
            ),
        )
        self.assertContains(
            response,
            reverse('stampaDocumento', kwargs={'pk': documento.pk}),
        )
        self.assertContains(response, 'Salda')

        Scadenze.objects.filter(SCCODICE=documento).update(SCPAGATA='S')
        response = self.client.get(reverse('corsi:iscrizioni'), filtri)
        self.assertContains(response, 'Sì')
        self.assertNotContains(response, 'class="btn btn-sm btn-success"')

    def test_enrollment_receipt_can_be_deleted(self):
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-iscrizione-da-eliminare',
        )
        self.riga_alunno.ricevuta_iscrizione = documento
        self.riga_alunno.save(update_fields=['ricevuta_iscrizione'])
        Scadenze.objects.create(
            SCCODICE=documento,
            SCNUMSCA=1,
            SCIMPSCA='20.00',
            SCPAGATA='N',
        )
        filtri = {
            'corso': str(self.corso.pk),
            'causale': self.causale.pk,
        }
        response = self.client.get(reverse('corsi:iscrizioni'), filtri)
        self.assertContains(response, 'Elimina ricevuta')
        self.assertContains(response, 'Elimina ricevute selezionate')

        response = self.client.post(
            reverse(
                'corsi:elimina-ricevuta-iscrizione',
                args=[self.riga_alunno.pk],
            ),
            filtri,
        )

        self.assertRedirects(
            response,
            reverse('corsi:iscrizioni')
            + f'?corso={self.corso.pk}&causale={self.causale.pk}',
        )
        self.assertFalse(Ord_Mast.objects.filter(pk=documento.pk).exists())
        self.assertFalse(Scadenze.objects.filter(SCCODICE=documento).exists())
        self.riga_alunno.refresh_from_db()
        self.assertIsNone(self.riga_alunno.ricevuta_iscrizione_id)

    def test_enrollment_receipts_can_be_bulk_deleted(self):
        altro_nominativo = Nominativi.objects.create(
            NOCODICE='CAL-STUDENT-3',
            NORAGSOC='Secondo alunno',
            NOCODNOM=settings.CCATCLI,
        )
        altra_iscrizione = Alunno.objects.create(
            corso=self.corso,
            alunno=altro_nominativo,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=45,
        )
        iscrizioni = (self.riga_alunno, altra_iscrizione)
        documenti = []
        for indice, iscrizione in enumerate(iscrizioni, start=1):
            documento = Ord_Mast.objects.create(
                DODATORD=date(2026, 10, 10),
                DOCODCAU=self.causale,
                DOCODINT=iscrizione.alunno,
                DOCODUTE=self.user,
                DOTIPDOC='RF',
                slug=f'ricevuta-iscrizione-multipla-{indice}',
            )
            iscrizione.ricevuta_iscrizione = documento
            iscrizione.save(update_fields=['ricevuta_iscrizione'])
            documenti.append(documento)
        filtri = {
            'corso': str(self.corso.pk),
            'causale': self.causale.pk,
        }
        altro_corso = Corso.objects.create(
            descrizione='Pianoforte',
            insegnante=self.corso.insegnante,
            prezzo='80.00',
            costo='40.00',
            data_inizio=date(2026, 10, 1),
            data_fine=date(2026, 12, 31),
        )

        response = self.client.post(
            reverse('corsi:elimina-ricevute-iscrizione-selezionate'),
            {
                'corso': str(altro_corso.pk),
                'causale': self.causale.pk,
                'iscrizioni_ids': [
                    str(iscrizioni[0].pk)
                ],
            },
        )
        self.assertEqual(
            Ord_Mast.objects.filter(
                pk__in=[documento.pk for documento in documenti]
            ).count(),
            2,
        )

        response = self.client.post(
            reverse('corsi:elimina-ricevute-iscrizione-selezionate'),
            {
                **filtri,
                'iscrizioni_ids': [
                    str(iscrizione.pk) for iscrizione in iscrizioni
                ],
            },
        )
        self.assertRedirects(
            response,
            reverse('corsi:iscrizioni')
            + f'?corso={self.corso.pk}&causale={self.causale.pk}',
        )
        self.assertFalse(
            Ord_Mast.objects.filter(
                pk__in=[documento.pk for documento in documenti]
            ).exists()
        )
        for iscrizione in iscrizioni:
            iscrizione.refresh_from_db()
            self.assertIsNone(iscrizione.ricevuta_iscrizione_id)

    def test_enrollment_receipt_linked_to_lessons_cannot_be_deleted(self):
        documento = Ord_Mast.objects.create(
            DODATORD=date(2026, 10, 10),
            DOCODCAU=self.causale,
            DOCODINT=self.alunno_nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='ricevuta-iscrizione-collegata-lezione',
        )
        self.riga_alunno.ricevuta_iscrizione = documento
        self.riga_alunno.save(update_fields=['ricevuta_iscrizione'])
        self.lezione.documento_fatturazione = documento
        self.lezione.save(update_fields=['documento_fatturazione'])

        response = self.client.post(
            reverse(
                'corsi:elimina-ricevuta-iscrizione',
                args=[self.riga_alunno.pk],
            ),
            {'corso': self.corso.pk, 'causale': self.causale.pk},
        )

        self.assertRedirects(
            response,
            reverse('corsi:iscrizioni')
            + f'?corso={self.corso.pk}&causale={self.causale.pk}',
        )
        self.assertTrue(Ord_Mast.objects.filter(pk=documento.pk).exists())
        self.riga_alunno.refresh_from_db()
        self.lezione.refresh_from_db()
        self.assertEqual(self.riga_alunno.ricevuta_iscrizione_id, documento.pk)
        self.assertEqual(self.lezione.documento_fatturazione_id, documento.pk)

    def test_monthly_attendance_report_renders_without_lessons(self):
        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {'anno': '2027', 'mese': '1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dettaglio_lezioni'], [])
        self.assertEqual(response.context['riepilogo_corsi'], [])
        self.assertEqual(response.context['riepilogo_alunni'], [])
        self.assertIsNotNone(response.context['totali'])
        self.assertEqual(response.context['totali']['minuti_assenza'], 0)

    def test_monthly_attendance_report_can_be_filtered_by_course(self):
        altro_corso = Corso.objects.create(
            descrizione='Pianoforte',
            insegnante=self.corso.insegnante,
            articolo=self.articolo,
            prezzo='80.00',
            costo='40.00',
            data_inizio=date(2026, 10, 1),
            data_fine=date(2026, 12, 31),
        )
        altro_alunno = Alunno.objects.create(
            corso=altro_corso,
            alunno=self.alunno_nominativo,
            giorno_settimana='martedi',
            ora_inizio='18:00',
            durata_minuti=60,
        )
        Lezioni.objects.create(
            alunno=altro_alunno,
            data=date(2026, 10, 13),
            data_ricorrenza=date(2026, 10, 13),
        )

        response = self.client.get(
            reverse('corsi:presenze-mensili'),
            {
                'anno': '2026',
                'mese': '10',
                'corso': str(altro_corso.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].is_valid())
        self.assertEqual(
            response.context['form'].cleaned_data['corso'],
            altro_corso,
        )
        self.assertEqual(len(response.context['dettaglio_lezioni']), 1)
        self.assertEqual(
            response.context['dettaglio_lezioni'][0]['corso'],
            altro_corso,
        )
        self.assertEqual(
            response.context['riepilogo_corsi'][0]['corso'],
            altro_corso,
        )
        self.assertEqual(response.context['totali']['minuti_alunni'], 60)
        self.assertContains(response, 'name="corso"')

    @patch('Corsi.forms.date')
    def test_monthly_attendance_report_defaults_to_next_month(self, mock_date):
        mock_date.today.return_value = date(2026, 10, 8)

        response = self.client.get(reverse('corsi:presenze-mensili'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['anno'], 2026)
        self.assertEqual(response.context['mese'], 11)
        self.assertIsNotNone(response.context['totali'])
