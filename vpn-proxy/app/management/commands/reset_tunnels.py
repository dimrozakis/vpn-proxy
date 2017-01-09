from django.core.management.base import BaseCommand
from app.models import Tunnel


class Command(BaseCommand):
    help = "Reset Tunnel(s)"

    def add_arguments(self, parser):
        parser.add_argument('tunnel', nargs='*', type=int)

    def handle(self, *args, **kwargs):
        if kwargs['tunnel']:
            tunnels = Tunnel.objects.filter(id__in=kwargs['tunnel'])
        else:
            tunnels = Tunnel.objects.all()
        for tunnel in tunnels:
            self.stdout.write("Resetting tunnel %d..." % tunnel.id)
            tunnel.reset()
