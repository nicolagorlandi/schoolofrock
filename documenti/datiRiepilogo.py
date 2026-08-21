from dataclasses import dataclass
from decimal import Decimal

# dati di riga castelletto IVA
@dataclass
class DatiRiepilogo:
    codice_iva: str = ''
    imponibile: Decimal = Decimal('0')
    imposta: Decimal = Decimal('0')
    percentuale_iva: Decimal = Decimal('0')
    imponibile_calcolo_ritenuta: Decimal = Decimal('0')
    esente: bool = False
    rev_charge: bool = False
    split_payment: bool = False

# totali documento (per calcolo castelletto iva e rateizzazione)
@dataclass
class totaliDocumento:
    totDocumento: Decimal = Decimal('0')
    totImposta: Decimal = Decimal('0')
    totImponibileEsente: Decimal = Decimal('0')
    totRitenuta: Decimal = Decimal('0')
    totBolli: Decimal = Decimal('0')


