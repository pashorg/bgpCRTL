from django.shortcuts import render
from facer.models import Machines, DoNotDistribute
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
import time
import telnetlib
from .conf import *


@login_required
# Add ip to blackhole list
def blackhole(request):
    machine_list = Machines.objects.all()
    blackhole_list = DoNotDistribute.objects.all()

    if request.POST.get('submit', False):
        try:
            # Create new entry in DB
            ip = request.POST.get('ip_addr', False)
            blackhole_exemplar = DoNotDistribute(ip_address=ip)
            blackhole_exemplar.save()

            # Load data to Quagga as static route with metric
            cmd = 'ip route ' + ip + ' 255.255.255.255 blackhole 254\n'
            response = load_to_quagga(quagga_ip, zebra_port, quagga_passwd, quagga_enable, cmd)

            # Return HTTP response
            blackhole_list = DoNotDistribute.objects.all()
            return render(request, 'facer/blackhole.html',
                          {
                              "machine_list": machine_list,
                              "blackhole_list": blackhole_list,
                              "response": response
                          }
                          )

        except IntegrityError as error:
            return render(request, 'facer/blackhole.html',
                          {
                              "machine_list": machine_list,
                              "blackhole_list": blackhole_list,
                              'error': error
                          }
                          )

    # Change selected IP
    if request.POST.get('update', False):
        try:
            # Load current data
            id = request.POST.get('blackhole_id', False)
            blackhole_exemplar = DoNotDistribute.objects.get(id=id)

            # Command to del from Quagga
            cmd = 'no ip route ' + blackhole_exemplar.ip_address + ' 255.255.255.255 blackhole 254\n'

            # Load new data into current DB entry
            blackhole_exemplar.ip_address = request.POST.get('ip_addr', False)
            blackhole_exemplar.save()

            # Command to load new data to Quagga
            cmd += 'ip route ' + blackhole_exemplar.ip_address + ' 255.255.255.255 blackhole 254\n'
            response = load_to_quagga(quagga_ip, zebra_port, quagga_passwd, quagga_enable, cmd)

            # Return HTTP response
            blackhole_list = DoNotDistribute.objects.all()
            return render(request, 'facer/blackhole.html',
                          {
                              "machine_list": machine_list,
                              "blackhole_list": blackhole_list,
                              "response": response
                          }
                          )

        except IntegrityError as error:
            return render(request, 'facer/blackhole.html',
                          {
                              "machine_list": machine_list,
                              "blackhole_list": blackhole_list,
                              'error': error
                          }
                          )

    # Delete entry
    if request.POST.get('delete', False):
        try:
            # Load selected IP
            id = request.POST.get('blackhole_id', False)
            blackhole_exemplar = DoNotDistribute.objects.get(id=id)

            # Delete selected IP from Quagga and DB
            cmd = 'no ip route ' + blackhole_exemplar.ip_address + ' 255.255.255.255 blackhole 254\n'
            response = load_to_quagga(quagga_ip, zebra_port, quagga_passwd, quagga_enable, cmd)
            blackhole_exemplar.delete()

            # Return HTTP response
            blackhole_list = DoNotDistribute.objects.all()
            return render(request, 'facer/blackhole.html',
                          {
                              "machine_list": machine_list,
                              "blackhole_list": blackhole_list,
                              "response": response
                          }
                          )

        except IntegrityError as error:
            return render(request, 'facer/blackhole.html',
                          {
                              "machine_list": machine_list,
                              "blackhole_list": blackhole_list,
                              'error': error
                          }
                          )

    return render(request, 'facer/blackhole.html',
                  {
                      "machine_list": machine_list,
                      "blackhole_list": blackhole_list
                  }
                  )


# Connect to Quagga via telnet and execute the following command
def load_to_quagga(quagga_ip, port, passwd, enable, cmd):
    tn = telnetlib.Telnet(quagga_ip, port)
    tn.read_until(b"Password: ").decode('utf-8')
    tn.write(passwd.encode('ascii') + b"\n")
    tn.read_until(b">").decode('utf-8')
    tn.write('en'.encode('ascii') + b"\n")
    if enable != '':
        tn.read_until(b"Password: ").decode('utf-8')
        tn.write(enable.encode('ascii') + b"\n")
    tn.read_until(b"#").decode('utf-8')
    tn.write('conf t'.encode('ascii') + b"\n")
    tn.read_until(b"#").decode('utf-8')

    cmd += 'end\n' \
           'wr\n'\
           'clear ip bgp * soft out\n'

    i = 0
    while i < len(cmd):
        if i + 100 < len(cmd):
            tn.write(cmd[i:i + 100].encode('ascii'))
        else:
            tn.write(cmd[i:len(cmd)].encode('ascii'))
        i += 100
        time.sleep(.1)

    output = tn.read_until(b"clear ip bgp * soft")
    output = output.replace(b'\r\n', b'<br>').decode('utf-8')
    return "Blackhole loaded: <br>" + output