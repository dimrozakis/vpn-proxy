from django.contrib import admin

from .models import Tunnel, Forwarding


class ForwardingAdmin(admin.ModelAdmin):
    fields = ['active', 'tunnel', 'dst_addr', 'dst_port', 'loc_port']
    readonly_fields = ['tunnel', 'dst_addr', 'dst_port', 'loc_port',
                       'updated_at', 'created_at']
    list_display = ['id', 'tunnel', 'dst_addr', 'dst_port', 'loc_port',
                    'active', 'created_at']
    actions = ['enable', 'disable']
    list_filter = ['active', 'tunnel', 'created_at', 'updated_at']

    def get_fields(self, request, obj=None):
        """If edit, enable display of readonly fields"""
        if obj:  # obj is not None, so this is an edit
            return ['active', 'tunnel', 'dst_addr', 'dst_port', 'loc_port',
                    'created_at', 'updated_at']
        return self.fields

    def get_readonly_fields(self, request, obj=None):
        """If edit, make fields readonly"""
        if obj:  # obj is not None, so this is an edit
            return self.readonly_fields
        return []

    def enable(self, request, queryset):
        for forwarding in queryset:
            forwarding.enable()

    def disable(self, request, queryset):
        for forwarding in queryset:
            forwarding.disable()


class AddForwardingInline(admin.TabularInline):
    model = Forwarding
    fields = ['dst_addr', 'dst_port', 'loc_port', 'active']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EditForwardingInline(admin.TabularInline):
    model = Forwarding
    fields = ['dst_addr', 'dst_port', 'loc_port', 'active']
    readonly_fields = ['dst_addr', 'dst_port', 'loc_port']

    def has_add_permission(self, request):
        return False


class TunnelAdmin(admin.ModelAdmin):
    readonly_fields = ['name', 'client', 'port',
                       'conf', 'client_conf', 'client_script',
                       'created_at', 'updated_at']
    list_display = ['name', 'server', 'client', 'port',
                    'forwardings', 'active', 'created_at']
    actions = ['enable', 'disable', 'reset', 'delete_selected']
    list_filter = ['active', 'created_at', 'updated_at']
    inlines = [EditForwardingInline, AddForwardingInline]

    def get_fieldsets(self, request, obj=None):
        """If edit, enable display of readonly fields"""
        if obj:  # obj is not None, so this is an edit
            return [
                (None, {
                    'fields': ('name', 'server', 'client', 'port', 'active',
                               'created_at', 'updated_at'),
                }),
                ('Extra', {
                    'fields': ('key', 'conf', 'client_conf', 'client_script'),
                    'classes': ('collapse', ),
                }),
            ]
        return [(None, {'fields': ('active', 'server', 'key')})]

    def forwardings(self, tunnel):
        return tunnel.forwarding_set.count()

    def enable(self, request, queryset):
        for tunnel in queryset:
            tunnel.enable()

    def disable(self, request, queryset):
        for tunnel in queryset:
            tunnel.disable()

    def reset(self, request, queryset):
        for tunnel in queryset:
            tunnel.reset()

    def delete_selected(self, request, queryset):
        for tunnel in queryset:
            tunnel.delete()
    delete_selected.short_description = "Delete"


admin.site.register(Tunnel, TunnelAdmin)
admin.site.register(Forwarding, ForwardingAdmin)
