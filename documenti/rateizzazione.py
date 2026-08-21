from dataclasses import dataclass, field
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import List, Optional, Union


#   Elemento che identifica una rata, quindi percentuale rispetto al totale
#   tipo scadenza (fine mese, inizio mese, data documento
#   intervallo di giorni da far passare rispetto alla rata precedente
#   Tipo pagamento (bonifico, rimessa, ect)
#   Importo minimo, se l'importo calcolato è inferiore la scadenza avrà il valore minimo

@dataclass
class ElementoRateizzazione:
    intervallo: int = 0
    tipo_pagamento: str = ''
    tipo: str = 'Data Doc.'
    minimo: Decimal = Decimal('0')
    percentuale: Decimal = Decimal('0')
    importo: Decimal = Decimal('0')
    pagata: str = 'N'
    giorno_del_mese: int = 0


#  Elemento che identifica la rata risultante, quindi importo e scadenza

@dataclass
class RateizzazioneResult:
    tipo_pagamento: str = ''
    importo: Decimal = Decimal('0')
    data_scadenza: Optional[date] = None
    pagata: str = 'N'
    data_pagamento: Optional[date] = None

# data inizio rappresenta da dove iniziare il calcolo
# importo importo globale da rateizzare
# definizione contiene la definizione delle rate
# risultato conterrà le rate determinata dalla routine calcolo
@dataclass
class Rateizzazione:
    datainizio: Optional[Union[date, datetime]] = None
    importo: Decimal = Decimal('0')
    arrotondamento: int = 0
    ritenuta_acconto: Decimal = Decimal('0')
    spese_in_prima_rata: bool = False

    definizione: List[ElementoRateizzazione] = field(default_factory=list)
    risultato: List[RateizzazioneResult] = field(default_factory=list)
    
    # calcola la rateizzazione
    def calcolo(self):
        self.risultato.clear()
        if not self.definizione:
            return

        totale = Decimal('0')
        meno = Decimal('0')
        data_scadenza = _as_date(self.datainizio)

        for elemento_definizione in self.definizione:
            risultato = RateizzazioneResult(
                tipo_pagamento=elemento_definizione.tipo_pagamento,
                pagata=elemento_definizione.pagata,
            )

            if elemento_definizione.importo == 0:
                importo_rata = _round_money(
                    self.importo
                    * (elemento_definizione.percentuale - meno)
                    / Decimal('100'),
                    self.arrotondamento,
                )
                risultato.importo = (
                    elemento_definizione.minimo
                    if elemento_definizione.minimo > 0
                    and elemento_definizione.minimo > importo_rata
                    else importo_rata
                )
            else:
                risultato.importo = elemento_definizione.importo

            if totale + risultato.importo > self.importo:
                risultato.importo = self.importo - totale

            totale += risultato.importo
            data_scadenza = _add_interval(
                data_scadenza,
                elemento_definizione.intervallo,
                elemento_definizione.tipo,
            )

            if elemento_definizione.giorno_del_mese > 0:
                data_scadenza = _set_day_of_month(
                    data_scadenza,
                    elemento_definizione.giorno_del_mese,
                )

            risultato.data_scadenza = data_scadenza
            if risultato.pagata == 'S':
                risultato.data_pagamento = risultato.data_scadenza

            self.risultato.append(risultato)
            if totale == self.importo:
                break

        if totale != self.importo and self.risultato:
            self.risultato[-1].importo = _round_money(
                self.risultato[-1].importo + self.importo - totale,
                self.arrotondamento,
            )

        if self.ritenuta_acconto > 0 and self.datainizio is not None:
            data_ritenuta = _end_of_month(_as_date(self.datainizio))
            data_ritenuta += timedelta(days=16)
            self.risultato.append(RateizzazioneResult(
                tipo_pagamento='Ritenuta Acconto',
                importo=self.ritenuta_acconto,
                data_scadenza=data_ritenuta,
            ))

    def empty(self):
        self.datainizio = None
        self.importo = Decimal('0')
        self.arrotondamento = 0
        self.ritenuta_acconto = Decimal('0')
        self.spese_in_prima_rata = False
        self.definizione.clear()
        self.risultato.clear()

    #Calcola le rate in base ai parametri passati
    def calcola_rate(
        self,
        nimporto: Decimal,
        spese: Decimal,
        interessi: Decimal,
        importo_rata: Decimal,
        ddal: Union[date, datetime],
        mesi: int,
        nrate: int,
        arrot: int,
        pagamento: str,
    ):
        self.empty()
        monte = nimporto + spese + interessi
        self.importo = monte
        self.datainizio = _add_months(_as_date(ddal), -mesi)
        self.arrotondamento = -arrot

        totale_percentuale = Decimal('100')
        for indice in range(nrate):
            elemento = ElementoRateizzazione(
                intervallo=30 * mesi,
                tipo_pagamento=pagamento,
            )

            if (
                indice == 0
                and spese + interessi > 0
                and self.spese_in_prima_rata
            ):
                elemento.minimo = max(spese + interessi, importo_rata)
                elemento.percentuale = max(
                    Decimal('100') / nrate,
                    Decimal('100') * elemento.minimo / self.importo,
                )
                totale_percentuale -= elemento.percentuale
            else:
                elemento.importo = importo_rata
                divisore = nrate
                if self.spese_in_prima_rata and spese + interessi > 0:
                    divisore -= 1
                elemento.percentuale = totale_percentuale / divisore

            self.definizione.append(elemento)

        percentuale_calcolata = sum(
            elemento.percentuale for elemento in self.definizione
        )
        if self.definizione and percentuale_calcolata != Decimal('100'):
            self.definizione[-1].percentuale += (
                Decimal('100') - percentuale_calcolata
            )


DateLike = Union[date, datetime]


def _as_date(value: Optional[DateLike]) -> date:
    if value is None:
        return date.today()
    return value.date() if isinstance(value, datetime) else value


def _round_money(value: Decimal, places: int) -> Decimal:
    exponent = Decimal('1').scaleb(-places)
    return value.quantize(exponent, rounding=ROUND_HALF_EVEN)


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _end_of_month(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def _start_of_month(value: date) -> date:
    return value.replace(day=1)


def _add_interval(value: date, interval: int, tipo: str) -> date:
    if interval % 30 == 0:
        new_date = _add_months(value, interval // 30)
    else:
        new_date = value + timedelta(days=interval)

    if tipo == 'Fine Mese':
        return _end_of_month(new_date)
    if tipo == 'Inizio Mese':
        return _start_of_month(new_date)
    return new_date


def _set_day_of_month(value: date, day: int) -> date:
    if value.day < day:
        return value + timedelta(days=day - value.day)
    if value.day > day:
        return _add_months(value, 1).replace(day=1) + timedelta(days=day - 1)
    return value