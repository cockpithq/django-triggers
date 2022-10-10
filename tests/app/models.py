from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template import Context, Template
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from triggers.models import Action, Condition, Event


class AppSession(models.Model):
    APP_MOBILE = 'mobile'
    APP_DESKTOP = 'desktop'
    APP_CHOICES = (
        (APP_MOBILE, _('Mobile')),
        (APP_DESKTOP, _('Desktop')),
    )

    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        verbose_name=_('user'),
        related_name='app_sessions',
        related_query_name='app_session',
    )
    app = models.CharField(_('application'), max_length=16, choices=APP_CHOICES)
    start_datetime = models.DateTimeField(_('started at'), db_index=True, default=timezone.now)

    class Meta:
        verbose_name = _('app session')
        verbose_name_plural = _('app sessions')

    def __str__(self):
        return f'{self.get_app_display()} at {date_format(self.start_datetime)}'


class Message(models.Model):
    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        verbose_name=_('user'),
        related_name='messages',
        related_query_name='message',
    )
    creation_datetime = models.DateTimeField(_('created at'), default=timezone.now)
    text = models.TextField(_('text'))

    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')

    def __str__(self):
        return f'{self.text[:10]} at {date_format(self.creation_datetime)}'


class AppSessionStartedEvent(Event):  # type: ignore[django-manager-missing]
    app = models.CharField(_('application'), max_length=16, choices=AppSession.APP_CHOICES, blank=True)

    class Meta:
        verbose_name = _('app session started')
        verbose_name_plural = _('app session started')

    def __str__(self):
        app_name: str = self.get_app_display() if self.app else _('any')
        return f'{app_name.capitalize()} {super().__str__()}'

    def should_be_fired(self, **kwargs) -> bool:
        if self.app:
            if kwargs.pop('app') != self.app:
                return False
        return super().should_be_fired(**kwargs)


class AppSessionCountCondition(Condition):  # type: ignore[django-manager-missing]
    app = models.CharField(_('application'), max_length=16, choices=AppSession.APP_CHOICES, blank=True)
    count = models.PositiveIntegerField(_('app session count'))

    class Meta:
        verbose_name = _('app session count')
        verbose_name_plural = _('app session count')

    def __str__(self):
        app_name: str = self.get_app_display() if self.app else _('any')
        return f'{app_name.capitalize()} {super().__str__()} is {self.count}'

    def is_satisfied(self, user) -> bool:
        app_sessions = user.app_sessions.all()
        if self.app:
            app_sessions = app_sessions.filter(app=self.app)
        return app_sessions.count() == self.count


@receiver(post_save, sender=AppSession)
def on_app_session_started(sender, instance: AppSession, **kwargs):
    transaction.on_commit(lambda: [
        event.fire_single(instance.user_id, app=instance.app)
        for event in AppSessionStartedEvent.objects.all()
    ])


class SendMessageAction(Action):  # type: ignore[django-manager-missing]
    text = models.TextField(_('text'))

    class Meta:
        verbose_name = _('send message')
        verbose_name_plural = _('send messages')

    def __str__(self):
        return f'{super().__str__()} {self.text}'

    def perform(self, user, context):
        text_template = Template(self.text)
        text = text_template.render(Context(context))
        user.messages.create(text=text)
