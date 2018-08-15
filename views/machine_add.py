from django.shortcuts import render
from facer.models import Machines
from django.db import IntegrityError
import re
import telnetlib
from .conf import *
from django.contrib.auth.decorators import login_required


@login_required
# Adding new host to DB
def machine_add(request):

    machine_list = Machines.objects.all()
    ip = ""
    description = ""
    community = ""

    # If data was submitted get all POST and add to DB
    if request.POST.get('submit', False):
        try:
            ip = request.POST['ip_addr']
            description = request.POST['descr']
            community = request.POST['community']
            remote_as = request.POST['remote_as']
            login = request.POST['login']
            password = request.POST['password']
            enable_password = request.POST['enable_password']
            machine = Machines(ip_address=ip, description=description, community_name=community, remote_as=remote_as,
                               login=login, password=password, enable_password=enable_password)
            machine.save()

            error = machine_load_to_quagga(ip, remote_as) + '<br><br>Добавлено!'

            return render(request, 'facer/machine_add.html',
                          {
                              "error": error,
                              "machine_list": machine_list,
                          }
                          )

        # If error during inserting return error
        except IntegrityError as error:
            return render(request, 'facer/machine_add.html',
                          {
                              'error': error,
                              "ip_address": ip,
                              "description": description,
                              "community_name": community,
                              "machine_list": machine_list,
                          }
                          )

    else:
        return render(request, 'facer/machine_add.html', {"machine_list": machine_list})


# Creating neighbor in Quagga via telnet
def machine_load_to_quagga(ip, remote_as):
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

    # BGP session on Quagga site is enabled
    # All distributions from host drop
    # Blackholed IPs selected by metric and sent with local community
    cmd = 'ip prefix-list AUTO-FROM-' + ip + ' seq 5 deny any\n' \
          'route-map AUTO-FROM-' + ip + ' permit 5\n' \
          ' match ip address prefix-list AUTO-FROM-' + ip + '\n' \
          ' exit\n' \
          'route-map AUTO-TO-' + ip + ' permit 65535\n' \
          ' match metric ' + bgpd_static_metric + '\n' \
          ' set community ' + bgpd_do_not_distribute_community + '\n' \
          ' exit\n' \
          'router bgp ' + local_as + '\n' \
          ' neighbor ' + ip + ' remote-as ' + remote_as + '\n' \
          ' neighbor ' + ip + ' soft-reconfiguration inbound\n' \
          ' neighbor ' + ip + ' route-map AUTO-FROM-' + ip + ' in\n' \
          ' neighbor ' + ip + ' route-map AUTO-TO-' + ip + ' out\n' \
          ' neighbor ' + ip + ' send-community\n'\
          'end\n' \
          'wr\n'
    tn.write(cmd.encode('ascii'))
    return "QUAGGA:<br>" + tn.read_until(b"Configuration saved").replace(b'\r\n', b'<br>').decode('utf-8')




















