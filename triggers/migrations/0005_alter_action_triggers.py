# Generated by Django 3.2.20 on 2024-06-04 05:14

from django.db import migrations, models
import django.db.models.deletion


def save_action_triggers(apps, schema_editor):
    Action = apps.get_model("triggers", "Action")
    for action in Action.objects.all():
        action.trigger_new_id = action.trigger_id
        action.save()


class Migration(migrations.Migration):

    dependencies = [
        ('triggers', '0004_alter_action_trigger'),
    ]

    operations = [
        migrations.RenameField(
            model_name='action',
            old_name='trigger',
            new_name='trigger_old',
        ),
        migrations.RenameField(
            model_name='action',
            old_name='trigger_new',
            new_name='trigger',
        ),
        migrations.AlterField(
            model_name='action',
            name='trigger',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='actions',
                                    related_query_name='action', to='triggers.trigger', verbose_name='trigger'),
        ),
        migrations.AlterField(
            model_name='action',
            name='trigger_old',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='actions_old', related_query_name='action_old', to='triggers.trigger',
                                    verbose_name='trigger obsolete'),
        ),
    ]
