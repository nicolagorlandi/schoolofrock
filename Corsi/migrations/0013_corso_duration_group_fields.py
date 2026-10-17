from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0012_insegnante_role_and_lesson_duration'),
    ]

    operations = [
        migrations.AddField(
            model_name='corso',
            name='durata_minuti',
            field=models.PositiveIntegerField(
                default=60,
                validators=[MinValueValidator(1)],
                verbose_name=_('Durata (minuti)'),
            ),
        ),
        migrations.AddField(
            model_name='corso',
            name='di_gruppo',
            field=models.BooleanField(default=False, verbose_name=_('Di gruppo')),
        ),
    ]
