from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Corso(models.Model):
    descrizione = models.CharField(max_length=80, blank=True)
    durata_minuti = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        verbose_name=_('Durata (minuti)'),
    )
    di_gruppo = models.BooleanField(default=False, verbose_name=_('Di gruppo'))
    insegnante = models.ForeignKey(
        'documenti.Nominativi',
        on_delete=models.PROTECT,
        related_name='corsi_insegnati',
    )
    articolo = models.ForeignKey(
        'documenti.Articoli',
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name='corsi',
    )
    prezzo = models.DecimalField(max_digits=10, decimal_places=2)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    data_inizio = models.DateField()
    data_fine = models.DateField()

    def __str__(self):
        cognome_insegnante = (
            self.insegnante.NOCOGNOM
            or self.insegnante.NORAGSOC
            or str(self.insegnante)
        )
        return ' '.join(
            parte for parte in (self.descrizione, cognome_insegnante) if parte
        )


class Alunno(models.Model):
    GIORNI_SETTIMANA = [
        ('lunedi', 'Lunedì'),
        ('martedi', 'Martedì'),
        ('mercoledi', 'Mercoledì'),
        ('giovedi', 'Giovedì'),
        ('venerdi', 'Venerdì'),
        ('sabato', 'Sabato'),
        ('domenica', 'Domenica'),
    ]

    corso = models.ForeignKey(
        Corso,
        on_delete=models.CASCADE,
        related_name='alunni',
    )
    alunno = models.ForeignKey(
        'documenti.Nominativi',
        on_delete=models.PROTECT,
        related_name='corsi_frequentati',
    )
    giorno_settimana = models.CharField(max_length=9, choices=GIORNI_SETTIMANA)
    ora_inizio = models.TimeField()
    durata_minuti = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    def __str__(self):
        return f'{self.alunno} - {self.get_giorno_settimana_display()} {self.ora_inizio}'


class Lezioni(models.Model):
    alunno = models.ForeignKey(
        Alunno,
        on_delete=models.CASCADE,
        related_name='lezioni',
    )
    data = models.DateField()
    data_ricorrenza = models.DateField(null=True, blank=True)
    ora_inizio = models.TimeField(null=True, blank=True)
    durata_minuti = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    presenza = models.BooleanField(
        default=False,
        choices=[(True, 'Sì'), (False, 'No')],
    )
    documento_fatturazione = models.ForeignKey(
        'documenti.Ord_Mast',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='lezioni_fatturate',
    )
    note = models.TextField(blank=True)

    def __str__(self):
        return f'Lezione del {self.data} - {self.alunno}'
