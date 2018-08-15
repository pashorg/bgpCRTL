from django.contrib import admin

# Register your models here.

from .models import Machines, Interfaces, Settings, Neighbours, Stats, RouteMaps, PrefixLists, RMtoPL

admin.site.register(Machines)
admin.site.register(Interfaces)
admin.site.register(Stats)
admin.site.register(Neighbours)
admin.site.register(Settings)
admin.site.register(RouteMaps)
admin.site.register(PrefixLists)
admin.site.register(RMtoPL)


