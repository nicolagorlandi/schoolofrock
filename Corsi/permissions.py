from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin


TEACHER_GROUP_NAME = 'Insegnante'


def is_insegnante(user):
    return (
        user.is_authenticated
        and user.groups.filter(name=TEACHER_GROUP_NAME).exists()
    )


class TeacherAccessMiddleware(MiddlewareMixin):
    allowed_views = {
        'home': {'GET'},
        'dashboard': {'GET'},
        'login': {'GET', 'POST'},
        'logout': {'GET'},
        'corsi:calendario-lezioni': {'GET'},
        'corsi:calendario-eventi': {'GET'},
        'corsi:aggiorna-presenza': {'POST'},
        'corsi:modifica-orario-lezione': {'POST'},
    }

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not is_insegnante(request.user):
            return None

        allowed_methods = self.allowed_views.get(
            request.resolver_match.view_name,
            set(),
        )
        if request.method not in allowed_methods:
            return HttpResponseForbidden(
                'Non hai i permessi per eseguire questa operazione.'
            )
        return None
