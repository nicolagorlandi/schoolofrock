from decimal import Decimal, ROUND_HALF_EVEN

from django.db.models import Max, Sum

from PaNet1Project import settings

from .models import (
    Azienda,
    Codiciva,
    MODPAGAM,
    Ord_dett,
    Rivadett,
    Scadenze,
)


TIPI_DOCUMENTO_CON_CASSA = {'FA', 'NC', 'FV', 'NV', 'OA', 'OV'}


def aggiorna_riga_cassa(documento):
    Ord_dett.objects.filter(
        DOCODICE=documento,
        DORIGCASSA=True,
    ).delete()

    intestatario = documento.DOCODINT
    percentuale_documento = documento.DO_CASSA or Decimal('0')
    baseImpRitenuta_documento = documento.DORITPIM or Decimal('0')
    if (
        documento.DOTIPDOC not in TIPI_DOCUMENTO_CON_CASSA
        or intestatario is None
        or percentuale_documento <= 0
        or baseImpRitenuta_documento<=0
    ):
        return

    articolo = Azienda.get_azienda().AZCODCAS
    if articolo is None:
        return

    riepiloghi, _ = documento.totale_fattura()
    base_imponibile = sum(
        (
            riepilogo.imponibile
            for riepilogo in riepiloghi
        ),
        Decimal('0'),
    )
    importo_cassa = (
        base_imponibile
        * baseImpRitenuta_documento
        / Decimal('100')
        * percentuale_documento
        / Decimal('100')
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    if importo_cassa <= 0:
        return

    ultimo_numero_riga = Ord_dett.objects.filter(
        DOCODICE=documento,
    ).aggregate(ultimo=Max('DONUMRIG'))['ultimo'] or 0
    Ord_dett.objects.create(
        DOCODICE=documento,
        DONUMRIG=ultimo_numero_riga + 1,
        DOCODART=articolo,
        DOQTAUM1=Decimal('1'),
        DOPREZZO=importo_cassa,
        DODESART=articolo.ARDESCRI,
        DODESSUP=(
            f'Cassa previdenziale {intestatario.NOCASSA}% '
            f'applicata al {percentuale_documento}%'
        ),
        DOCODIVA=documento.DOTCOIVA or articolo.ARCODIVA,
        DORIGCASSA=True,
    )


def aggiorna_castelletto_iva(documento, castelletto_iva):
    if documento.DOCODCAU.CDGESIVA != 1:
        return

    Rivadett.objects.filter(RICODICE=documento).delete()
    for dettaglio in castelletto_iva:
        Rivadett.objects.create(
            RICODICE=documento,
            RICODIVA=Codiciva.objects.get(pk=dettaglio.codice_iva),
            RIIMPONI=dettaglio.imponibile,
            RIIMPOST=dettaglio.imposta,
        )


def ricalcola_scadenze(
    documento,
    totale,
    form,
    acconto,
    finanziamento,
    cambio_data,
    vecchio_pagamento=None,
):
    totale_documento = totale.totDocumento
    if documento.DOCODCAU.CD_CICLO == 'A':
        totale_documento += totale.totRitenuta
    totale_documento -= acconto + finanziamento + totale.totBolli

    scadenze_esistenti = Scadenze.objects.filter(
        SCCODICE=documento
    ).aggregate(
        totale=Sum('SCIMPSCA'),
        pagata=Max('SCPAGATA'),
    )
    totale_scadenze = scadenze_esistenti['totale'] or Decimal('0')
    scadenza_pagata = scadenze_esistenti['pagata'] or False

    if (
        not cambio_data
        and totale_scadenze == totale_documento
        and vecchio_pagamento == documento.DOCODPAG
    ):
        return

    if scadenza_pagata == 'S':
        form.add_error(
            None,
            f'Il totale scadenze {totale_scadenze} è differente rispetto al '
            f'totale documento {totale_documento} ed esiste almeno una '
            'scadenza saldata.',
        )
        return

    Scadenze.objects.filter(SCCODICE=documento).delete()
    pagamento = documento.DOCODPAG
    if pagamento is None or totale_documento == 0:
        return

    rateizzazione = pagamento.legge_rateizzazione()
    rateizzazione.datainizio = documento.DODATORD
    rateizzazione.importo = (
        totale.totDocumento - acconto - finanziamento - totale.totBolli
    )
    if documento.DOCODCAU.CD_CICLO == 'A':
        rateizzazione.ritenuta_acconto = totale.totRitenuta
    if rateizzazione.definizione:
        rateizzazione.definizione[0].minimo = totale.totIMposta
    rateizzazione.calcolo()

    for indice, risultato in enumerate(rateizzazione.risultato, start=1):
        tipo_pagamento = None
        if risultato.tipo_pagamento:
            tipo_pagamento = MODPAGAM.objects.filter(
                MPCODICE=risultato.tipo_pagamento
            ).first()

        Scadenze.objects.create(
            SCCODICE=documento,
            SCNUMSCA=indice,
            SCDATSCA=risultato.data_scadenza,
            SCIMPSCA=risultato.importo,
            SCTIPPAG=tipo_pagamento,
            SCPAGATA=risultato.pagata,
            SCDATPAG=risultato.data_pagamento,
        )


def finalizza_documento(
    documento,
    form,
    *,
    acconto=None,
    finanziamento=None,
    vecchia_data=None,
    vecchio_pagamento=None,
):
    castelletto_iva, totale = documento.totale_fattura()
    aggiorna_castelletto_iva(documento, castelletto_iva)
    ricalcola_scadenze(
        documento,
        totale,
        form,
        acconto or Decimal('0'),
        finanziamento or Decimal('0'),
        vecchia_data != documento.DODATORD,
        vecchio_pagamento,
    )
    if documento.DOCODCAU.CDTIPINT == settings.CCATFOR:
        documento.DORITACC = totale.totRitenuta
        documento.save(update_fields=['DORITACC'])

    return totale
