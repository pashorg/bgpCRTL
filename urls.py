from django.urls import path

from . import views

app_name = 'facer'
urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('<int:Machines_id>/', views.detail, name='detail'),
    path('Machine_add/', views.machine_add, name='machine_add'),
    path('Machine_del/', views.machine_del, name='machine_del'),
    path('<int:Machines_id>/interface_add/', views.interface_add, name='interface_add'),
    path('interfaces_check/', views.interfaces_check, name='interfaces_check'),
    path('interfaces_stats/', views.interfaces_stats, name='interfaces_stats'),
    path('<int:Machines_id>/route_map_add/', views.route_map_add, name='route_map_add'),
    path('<int:Machines_id>/settings_set/', views.settings_set, name='settings_set'),
    path('blackhole/', views.blackhole, name='blackhole'),
]
