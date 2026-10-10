import json
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import load_workbook

from documenti.exports import esporta_tabelle_excel
from documenti.models import Causdocu, MenuItem, Nominativi, Ord_Mast, PAGAMENTI
from documenti.views import nominativi, nominativi_list_url
from PaNet1Project import settings


class EsportazioneExcelTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def post(self, payload, user=None):
        payload.setdefault('page_name', 'elenco')
        request = self.factory.post(
            '/export/excel/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        request.user = user or SimpleNamespace(is_authenticated=True)
        return esporta_tabelle_excel(request)

    def test_esporta_tabelle_su_fogli_separati_e_protegge_le_formule(self):
        response = self.post({
            'sheets': [
                {'name': 'Riepilogo', 'rows': [['Corso', 'Costo'], ['=1+1', '12,50']]},
                {'name': 'Riepilogo', 'rows': [['Alunno'], ['Mario Rossi']]},
            ]
        })

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.sheetnames, ['Riepilogo', 'Riepilogo (2)'])
        self.assertEqual(workbook['Riepilogo']['A2'].value, '=1+1')
        self.assertEqual(workbook['Riepilogo']['A2'].data_type, 's')
        self.assertEqual(workbook['Riepilogo']['B2'].value, 12.5)
        self.assertEqual(workbook['Riepilogo (2)']['A2'].value, 'Mario Rossi')

    @patch('documenti.exports.timezone.localtime')
    def test_nome_file_usa_pagina_e_timestamp(self, localtime):
        localtime.return_value = datetime(2025, 1, 2, 3, 4, 5)
        response = self.post({
            'page_name': 'presenze-mensili',
            'sheets': [{'name': 'Riepilogo', 'rows': [['Corso'], ['Chitarra']]}],
        })

        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="presenze-mensili_20250102_030405.xlsx"',
        )

    def test_rifiuta_nome_pagina_non_valido(self):
        response = self.post({
            'page_name': '../presenze',
            'sheets': [{'name': 'Elenco', 'rows': [['Corso'], ['Chitarra']]}],
        })

        self.assertEqual(response.status_code, 400)

    def test_richiede_autenticazione(self):
        response = self.post(
            {'sheets': [{'name': 'Elenco', 'rows': [['Colonna'], ['Dato']]}]},
            user=SimpleNamespace(is_authenticated=False),
        )

        self.assertEqual(response.status_code, 302)

    def test_rifiuta_payload_non_valido(self):
        response = self.post({'sheets': []})

        self.assertEqual(response.status_code, 400)


class NominativiListUrlTests(SimpleTestCase):
    def test_cliente_and_fornitore_types_resolve_to_existing_lists(self):
        self.assertEqual(nominativi_list_url(settings.CCATCLI), '/doc/clienti')
        self.assertEqual(nominativi_list_url(settings.CCATFOR), '/doc/fornitori')

    def test_unsupported_type_is_reported(self):
        with self.assertRaises(ValueError):
            nominativi_list_url('OTHER')


class NominativiSearchTests(TestCase):
    def test_search_filters_combine_across_requested_fields(self):
        match = Nominativi.objects.create(
            NOCODICE='ROSSI_MARIO',
            NOCODNOM=settings.CCATCLI,
            slug='rossi-mario',
            NOCODFIS='RSSMRA80A01H501U',
            NOPARIVA='01234567890',
            NO_NOME='Mario',
            NOCOGNOM='Rossi',
            NOTELEF2='3331234567',
            NO_CITTA='Roma',
        )
        Nominativi.objects.create(
            NOCODICE='BIANCHI_MARIO',
            NOCODNOM=settings.CCATCLI,
            slug='bianchi-mario',
            NOCODFIS='BNCMRA80A01H501U',
            NO_NOME='Mario',
            NOCOGNOM='Bianchi',
            NOTELEF1='3337654321',
            NO_CITTA='Milano',
        )

        request = RequestFactory().get(
            '/doc/clienti',
            {
                'nome': 'mar',
                'cognome': 'ross',
                'telefono': '333123',
                'citta': 'rom',
                'codice_fiscale': 'RSSMRA',
                'partita_iva': '012345',
            },
        )
        request.user = AnonymousUser()

        with patch('documenti.views.render') as render:
            nominativi(request, settings.CCATCLI)

        context = render.call_args.args[2]
        self.assertEqual(list(context['Nominativi']), [match])
        self.assertEqual(context['filtri']['citta'], 'rom')


class CausdocuManagementTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='causdocu-manager')
        permission = Permission.objects.get(
            content_type__app_label='documenti',
            codename='Manager_Ordini',
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)
        self.user = user

    def causale_form_data(self, **overrides):
        data = {
            'CDCODICE': 'TST01',
            'CDDESCRI': 'Causale test',
            'CD_CICLO': 'V',
            'CDTIPDOC': 'RF',
            'CDTIPINT': settings.CCATCLI,
            'CDCAUMAG': '',
            'CDNUMAUT': '1',
            'CDQUALIT': '0',
            'CDINTOBB': '1',
            'CDGESIVA': '1',
            'CDGESPAG': '1',
        }
        data.update(overrides)
        return data

    def test_menu_places_document_causals_under_archives_documents(self):
        voce = MenuItem.objects.get(
            label='Causali Documenti',
            url_name='causali-documenti-list',
        )

        self.assertEqual(voce.parent.label, 'Documenti')
        self.assertEqual(voce.parent.parent.label, 'Archivi')

    def test_create_and_update_document_causal(self):
        pagamento = PAGAMENTI.objects.create(
            PACODICE='TESTP',
            PADESCRI='Pagamento predefinito test',
            slug='testp',
        )
        response = self.client.post(
            reverse('causali-documenti-create'),
            self.causale_form_data(CDPAGDEF=pagamento.pk),
        )

        self.assertRedirects(response, reverse('causali-documenti-list'))
        causale = Causdocu.objects.get(pk='TST01')
        self.assertEqual(causale.slug, 'tst01')
        self.assertEqual(causale.CDPAGDEF, pagamento)

        response = self.client.post(
            reverse('causali-documenti-update', args=[causale.pk]),
            self.causale_form_data(
                CDDESCRI='Descrizione aggiornata',
                CDPAGDEF=pagamento.pk,
            ),
        )

        self.assertRedirects(response, reverse('causali-documenti-list'))
        causale.refresh_from_db()
        self.assertEqual(causale.CDDESCRI, 'Descrizione aggiornata')

    def test_list_filters_document_causals_by_cycle_type_description_and_code(self):
        Causdocu.objects.create(
            CDCODICE='RF001',
            CDDESCRI='Ricevuta fiscale',
            CD_CICLO='V',
            CDTIPDOC='RF',
            CDQUALIT=0,
            slug='rf001',
        )
        Causdocu.objects.create(
            CDCODICE='FA001',
            CDDESCRI='Fattura acquisto',
            CD_CICLO='A',
            CDTIPDOC='FA',
            CDQUALIT=0,
            slug='fa001',
        )

        response = self.client.get(
            reverse('causali-documenti-list'),
            {
                'ciclo': 'V',
                'tipo_documento': 'rf',
                'descrizione': 'fisc',
                'codice': '001',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['causali_documento'].values_list(
                'CDCODICE',
                flat=True,
            )),
            ['RF001'],
        )
        self.assertContains(response, 'value="fisc"')
        self.assertContains(response, 'value="001"')

    def test_selected_causal_returns_its_default_payment(self):
        pagamento = PAGAMENTI.objects.create(
            PACODICE='CAUPG',
            PADESCRI='Pagamento causale',
            slug='caupg',
        )
        causale = Causdocu.objects.create(
            CDCODICE='CAU01',
            CDDESCRI='Causale con pagamento',
            CDTIPDOC='RF',
            CDQUALIT=0,
            CDPAGDEF=pagamento,
            slug='cau01',
        )

        response = self.client.get(
            reverse('leggiCausale'),
            {'causaleId': causale.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'DOCODPAG': pagamento.pk})

        causale.CDPAGDEF = None
        causale.save(update_fields=['CDPAGDEF'])
        response = self.client.get(
            reverse('leggiCausale'),
            {'causaleId': causale.pk},
        )
        self.assertEqual(response.json(), {'DOCODPAG': None})

    def test_cannot_delete_document_causal_used_by_a_document(self):
        causale = Causdocu.objects.create(
            CDCODICE='TST02',
            CDDESCRI='Causale in uso',
            CDTIPDOC='RF',
            CDQUALIT=0,
            slug='tst02',
        )
        nominativo = Nominativi.objects.create(
            NOCODICE='TST-CLIENT',
            NORAGSOC='Cliente test',
            NOCODNOM=settings.CCATCLI,
        )
        documento = Ord_Mast.objects.create(
            DOCODCAU=causale,
            DOCODINT=nominativo,
            DOCODUTE=self.user,
            DOTIPDOC='RF',
            slug='documento-test-causale',
        )

        response = self.client.post(
            reverse('causali-documenti-delete', args=[causale.pk]),
            follow=True,
        )

        self.assertContains(response, 'è utilizzata da documenti')
        self.assertTrue(Causdocu.objects.filter(pk=causale.pk).exists())
        self.assertTrue(Ord_Mast.objects.filter(pk=documento.pk).exists())
