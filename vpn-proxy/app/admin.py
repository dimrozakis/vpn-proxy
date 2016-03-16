from django.contrib import admin

from .models import Tunnel, Forwarding


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


class ForwardingAdmin(admin.ModelAdmin):
    fields = ['src_addr', 'dst_addr', 'dst_port', 'loc_port', 'tunnel']
    list_display = ['id', 'src_addr', 'dst_addr',
                    'dst_port', 'loc_port', 'created_at']
    actions = ['enable', 'disable']

    def enable(self, request, queryset):
        for forwarding in queryset:
            forwarding.enable()

    def disable(self, request, queryset):
        for forwarding in queryset:
            forwarding.disable()


admin.site.register(Tunnel, TunnelAdmin)
admin.site.register(Forwarding, ForwardingAdmin)
