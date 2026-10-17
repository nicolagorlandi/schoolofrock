from django.core.validators import MinValueValidator
from django.db import migrations, models


def create_teacher_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(
        name='Insegnante'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Corsi', '0011_alter_lezioni_documento_fatturazione'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='lezioni',
            name='durata_minuti',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1)],
            ),
        ),
        migrations.RunPython(create_teacher_group, migrations.RunPython.noop),
    ]
