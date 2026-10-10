from decimal import Decimal

from django.db.models import Max, Sum

from PaNet1Project import settings

from .models import Codiciva, MODPAGAM, Rivadett, Scadenze


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
