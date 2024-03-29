# Generated by Django 3.2.18 on 2023-03-13 13:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('triggers', '0003_event_delay'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClockEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='triggers.event')),
            ],
            options={
                'abstract': False,
                'base_manager_name': 'objects',
            },
            bases=('triggers.event',),
        ),
        migrations.CreateModel(
            name='HasUncompletedTaskCondition',
            fields=[
                ('condition_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='triggers.condition')),
            ],
            options={
                'abstract': False,
                'base_manager_name': 'objects',
            },
            bases=('triggers.condition',),
        ),
        migrations.CreateModel(
            name='SendEmailAction',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='triggers.action')),
                ('subject', models.CharField(max_length=256, verbose_name='subject')),
                ('message', models.TextField(help_text='You can use the Django template language.', verbose_name='message')),
            ],
            options={
                'abstract': False,
                'base_manager_name': 'objects',
            },
            bases=('triggers.action',),
        ),
        migrations.CreateModel(
            name='TaskCompletedEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='triggers.event')),
                ('important_only', models.BooleanField(default=False, verbose_name='important only')),
            ],
            options={
                'verbose_name': 'task completed',
                'abstract': False,
                'base_manager_name': 'objects',
            },
            bases=('triggers.event',),
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='name')),
                ('is_completed', models.BooleanField(db_index=True, default=False, verbose_name='completed')),
                ('is_important', models.BooleanField(default=False, verbose_name='important')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', related_query_name='task', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'task',
                'verbose_name_plural': 'tasks',
            },
        ),
    ]
