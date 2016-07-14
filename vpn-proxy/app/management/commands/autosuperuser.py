from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Create superuser if missing (Non Interactive)."

    def add_arguments(self, parser):
        parser.add_argument('username', default='admin', nargs='?')
        parser.add_argument('password', default='admin', nargs='?')
        parser.add_argument('-e', '--email')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        password = kwargs.get('password') or username
        email = kwargs.get('email') or '%s@example.com' % username
        try:
            User.objects.get(username=username)
            self.stdout.write("User '%s' already exists." % username)
        except User.DoesNotExist:
            self.stdout.write("Creating user '%s' (%s) with password '%s'." %
                              (username, email, password))
            User.objects.create_superuser(username, email, password)
