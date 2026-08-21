from decimal import Decimal, ROUND_HALF_EVEN

# riceve l'importo e la percentuale e ritorna la parte imponibila
# es dato 120 e 20 ritorna 100 (100 + 100*20/100)=120
# nround rappresenta i decimali per arrontondare...
def scorporo(importo, percentuale, decimali=2):
    """Calcola l'imponibile netto partendo da un importo IVA inclusa."""
    importo = Decimal(importo)
    percentuale = Decimal(percentuale)

    quantizzazione = Decimal('1').scaleb(-decimali)

    if percentuale == 0:
        valore = importo
    else:
        valore = importo * Decimal('100') / (
            Decimal('100') + percentuale
        )

    return valore.quantize(
        quantizzazione,
        rounding=ROUND_HALF_EVEN,
    )