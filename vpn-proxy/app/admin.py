from django.contrib import admin

from .models import Tunnel


class TunnelAdmin(admin.ModelAdmin):
    fields = ['server', 'key']
    readonly_fields = ['name', 'active', 'client', 'port',
                       'conf', 'client_conf', 'client_script', 'created_at']
    list_display = ['name', 'server', 'client', 'port', 'active']
    actions = ['start', 'stop', 'reset', 'delete_selected']

    def get_fields(self, request, obj=None):
        """If edit, enable display of readonly fields"""
        if obj:  # obj is not None, so this is an edit
            return ['name', 'active', 'server', 'client', 'port', 'key',
                    'conf', 'client_conf', 'client_script', 'created_at']
        return self.fields

    def start(self, request, queryset):
        for tunnel in queryset:
            tunnel.start()

    def stop(self, request, queryset):
        for tunnel in queryset:
            tunnel.stop()

    def reset(self, request, queryset):
        for tunnel in queryset:
            tunnel.reset()

    def delete_selected(self, request, queryset):
        for tunnel in queryset:
            tunnel.delete()
    start.short_description = "Delete"


admin.site.register(Tunnel, TunnelAdmin)
