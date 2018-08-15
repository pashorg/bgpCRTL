from django.shortcuts import get_object_or_404, render
from django.db import IntegrityError
from facer.models import Machines, Interfaces, Stats, RMtoPL, RouteMaps, PrefixLists, Settings
from django.contrib.auth.decorators import login_required
from .prefix_func import *


# Deleting host from DB
@login_required
def machine_del(request):
    machine_list = Machines.objects.all()
    if request.POST.get('submit', False):
        response = ''
        id = request.POST.get('id', False)  # Host id to delete
        try:
            current_machine = Machines.objects.get(id=id)
            settings_to_delete = Settings.objects.filter(m_id=id)  # Settings to delete
            response += 'Удаляем настройки:<br>'
            for current_settings in settings_to_delete:
                response += prefix_delete_from_host(current_settings.id) + '<br><br>'  # Del prefix-lists from host
                response += prefix_delete_from_quagga(current_settings.id) + '<br><br>'  # Del prefix-lists from Quagga
                response += prefix_delete(current_settings.id)  # Del prefix-lists from DB
                response += current_settings.net + '/' + str(current_settings.net_mask) + ' удалено<br>'
                current_settings.delete()  # Del settings from DB

            # Delete host's route-maps
            response += 'Удаляем route-maps:<br>'
            route_maps_to_delete = RouteMaps.objects.filter(m_id=id)
            for route_map in route_maps_to_delete:
                response += 'Route-map ' + route_map.name + ' удален<br>'
                route_map.delete()

            # Delete host's stats and interfaces
            response += 'Удаляем интерфейсы:'
            interfaces_to_delete = Interfaces.objects.filter(m_id=id)
            for interface in interfaces_to_delete:
                stats_to_delete = Stats.objects.filter(i_id=interface.id)
                stats_to_delete.delete()
                response += 'Статистика удалена<br>'
                response += 'Интерфейс ' + interface.name + ' удален<br>'
                interface.delete()

            # Delete host from Quagga neighbours
            response += machine_del_from_quagga(current_machine.ip_address, current_machine.remote_as)
            response += 'Хост ' + current_machine.ip_address + ' - ' + current_machine.description + ' удален<br>'
            current_machine.delete()

        except (Machines.DoesNotExist, IntegrityError) as error:
            response += str(error)

    else:
        response = 'Хост не был выбран'

    return render(request, 'facer/machine_del.html',
                  {
                      'error': response,
                      "machine_list": machine_list,
                  }
                  )


# Delete host from Quagga via telnet
def machine_del_from_quagga(ip, remote_as):
    tn = telnetlib.Telnet(quagga_ip, bgpd_port)
    tn.read_until(b"Password: ").decode('utf-8')
    tn.write(bgpd_passwd.encode('ascii') + b"\n")
    tn.read_until(b">").decode('utf-8')
    tn.write('en'.encode('ascii') + b"\n")
    if bgpd_enable != '':
        tn.read_until(b"Password: ").decode('utf-8')
        tn.write(bgpd_enable.encode('ascii') + b"\n")
    tn.read_until(b"#").decode('utf-8')
    tn.write('conf t'.encode('ascii') + b"\n")
    tn.read_until(b"#").decode('utf-8')

    cmd = 'no ip prefix-list AUTO-FROM-' + ip + ' seq 5 deny any\n' \
          'no route-map AUTO-FROM-' + ip + ' permit 5\n' \
          'router bgp ' + local_as + '\n' \
          ' no neighbor ' + ip + ' remote-as ' + str(remote_as) + '\n' \
          ' no neighbor ' + ip + ' soft-reconfiguration inbound\n' \
          ' no neighbor ' + ip + ' route-map AUTO-FROM-' + ip + ' in\n' \
          ' no neighbor ' + ip + ' route-map AUTO-TO-' + ip + ' out\n' \
          'end\n' \
          'wr\n'

    tn.write(cmd.encode('ascii'))
    return "QUAGGA:<br>" + tn.read_until(b"Configuration saved").replace(b'\r\n', b'<br>').decode('utf-8')