# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_auto_20160316_1617'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='forwarding',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='tunnel',
            options={'ordering': ['-created_at']},
        ),
    ]
