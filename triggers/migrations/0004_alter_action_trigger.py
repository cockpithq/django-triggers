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
        ('triggers', '0003_event_delay'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='trigger_new',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='actions_new',
                                    related_query_name='action_new', to='triggers.trigger', verbose_name='trigger'),
        ),
        migrations.RunPython(save_action_triggers, reverse_code=migrations.RunPython.noop),
    ]
