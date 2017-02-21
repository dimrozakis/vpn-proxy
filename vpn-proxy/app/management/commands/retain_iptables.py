from django.core.management.base import BaseCommand
from app.models import Forwarding

import datetime


class Command(BaseCommand):
    help = "Trigger IPtables retention."

    def add_arguments(self, parser):
        parser.add_argument('tunnel', nargs='*', type=int)
        parser.add_argument('--time', default=(60 * 60 * 24), type=int)

    def handle(self, *args, **kwargs):
        query = {}
        query['updated_at__lt'] = (
            datetime.datetime.utcnow() -
            datetime.timedelta(seconds=kwargs['time'])
        )
        if kwargs['tunnel']:
            query['tunnel_id__in'] = kwargs['tunnel']
        for frule in Forwarding.objects.filter(**query):
            self.stdout.write("Disabling %s..." % frule)
            frule.disable()
