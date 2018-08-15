from django.shortcuts import render
from facer.models import Interfaces, Stats, Machines
from datetime import datetime
from django.db import IntegrityError
from easysnmp import Session
from easysnmp import EasySNMPTimeoutError


# Reading interfaces stats via snmp
def interfaces_stats(request):
    machine_list = Machines.objects.all()
    all_interfaces = Interfaces.objects.all().order_by('m_id', 'snmp_number')
    response = {}
    i = 0

    # Checking for all known interfacs on all hosts
    for interface in all_interfaces:
        in_oid = '.1.3.6.1.2.1.2.2.1.10.' + str(interface.snmp_number)
        out_oid = '.1.3.6.1.2.1.2.2.1.16.' + str(interface.snmp_number)

        # Get ip address and credentials from DB
        machine = Machines.objects.get(pk=interface.m_id)
        ip = machine.ip_address
        community = machine.community_name
        try:
            session = Session(hostname=ip, community=community, version=2)

            counter_in = session.get(in_oid).value
            counter_out = session.get(out_oid).value

            stat = Stats(i_id=interface.id, counter_in=counter_in, counter_out=counter_out,
                         timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            stat.save()
            response[i] = {
                'ip': ip,
                'interface': interface.name,
                'counter_in': counter_in,
                'counter_out': counter_out,
                'status': 'OK'
            }
            i += 1

        except (IntegrityError, ValueError, EasySNMPTimeoutError) as error:
            response[i] = {
                'ip': ip,
                'interface': interface.name,
                'counter_in': counter_in,
                'counter_out': counter_out,
                'status': error
            }
            i += 1

    return render(request, 'facer/interfaces_stats.html',
                      {
                          'machine_list': machine_list,
                          'response': response
                      })
