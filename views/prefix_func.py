from facer.models import Machines, Settings, PrefixLists, RMtoPL, RouteMaps
from django.db import IntegrityError
from django.db.models import Max
import telnetlib
import paramiko
import time
from .conf import *


# Telnet connection to Quagga
def tn_connect():
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
    return tn


# Send command via telnet
def tn_send(tn, cmd):
    i = 0
    while i < len(cmd):
        if i + 100 < len(cmd):
            tn.write(cmd[i:i + 100].encode('ascii'))
        else:
            tn.write(cmd[i:len(cmd)].encode('ascii'))
        i += 100
        time.sleep(.1)
    return 1


# Send command via ssh
def ssh_send(shell, cmd):
    i = 0
    while i < len(cmd):
        if i + 100 < len(cmd):
            shell.send(cmd[i:i + 100])
        else:
            shell.send(cmd[i:len(cmd)])
        i += 100
        time.sleep(.1)
    return 1


# ssh or Telnet connection to host
def ssh_or_tn(m_id):
    current_machine = Machines.objects.get(id=m_id)
    output = ''

    # Connect data
    host = current_machine.ip_address
    user = current_machine.login
    secret = current_machine.password
    port = 22
    enable = current_machine.enable_password

    try:
        # Try SSH
        output += 'Try SSH<br>'
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=user, password=secret, port=port, timeout=3)
        output += 'SSH OK!<br> '

        shell = client.invoke_shell(height=0, width=256)

        # Send enable + passwd
        shell.send("enable\n")
        if enable:
            tmp = shell.recv(1000)
            while tmp.lower().find(b'password') == -1:
                tmp += shell.recv(1000)
            shell.send(enable + '\n')
        output += tmp.decode('utf-8')

        tmp = shell.recv(1000)
        while tmp.lower().find(b'#') == -1:
            tmp += shell.recv(1000)
        output += tmp.decode('utf-8')
        tn = ''

        return output, client, shell, tn

    # If SSH results as error then try Telnet
    except (TimeoutError, paramiko.AuthenticationException, ConnectionRefusedError, Exception) as error:
        output += str(error)
        try:
            output += '<br>Try Telnet<br>'
            tn = telnetlib.Telnet(host, 23)
            tn.read_until(b"Username: ")
            tn.write(user.encode('ascii') + b"\n")
            tn.read_until(b"Password: ")
            tn.write(secret.encode('ascii') + b"\r\n")
            tn.read_until(b">")
            output += 'Telnet OK!<br>'

            tn.write("enable\n".encode('ascii'))
            if enable:
                output += tn.read_until(b"Password: ").decode('utf-8')
                tn.write(enable.encode('ascii') + b"\r\n")
            output += tn.read_until(b'#').decode('utf-8')
            client = shell = ''

            return output, client, shell, tn

        except (TimeoutError, EOFError, ConnectionRefusedError) as error:
            output += str(error) + '<br>'
            output = client = shell = tn = ''
            return output, client, shell, tn


# Creating prefix-list in DB from settings net
def prefix_create(settings_id):
    current_settings = Settings.objects.get(id=settings_id)
    net = current_settings.net
    net_mask = current_settings.net_mask
    prefix = current_settings.max_prefix

    # split net by dots
    net = net.split('.')
    net_bits = ''

    # Turn to bits
    for el in net:
        net_bits += format(int(el), '08b')

    net_int = int(net_bits[0:prefix], 2)  # net as an int lengthen as max prefix

    # Prefix-list unique id inside route-map
    prefixes = PrefixLists.objects.filter(m_id=current_settings.m_id)
    if prefixes:
        seq = prefixes.aggregate(Max('rm_seq'))
        seq = seq['rm_seq__max'] + 1
    else:
        seq = 1
    response = ''

    name = 'AUTO_PREFIX_' + str(current_settings.m_id) + '_' + current_settings.net + '_FULL'

    # Adding full net as prefix-list
    try:
        prefix_list_full = PrefixLists(name=name, net=current_settings.net, net_mask=current_settings.net_mask
                                       , rm_seq=seq, m_id=current_settings.m_id, s_id=current_settings.id)
        prefix_list_full.save()
        response += name + ' создан <br>'
    except IntegrityError as error:
        response += error + ' <br>'

    # Creating other prefix-lists (all subnets with longer mask)
    # Cut net is taken and increased by 1 for n times
    # Where n = 2^(diff between subnet mask and net mask)
    for i in range(1, 2**(prefix - net_mask)+1):
        seq += 1
        sub_net_bits = format(net_int, '0'+str(prefix)+'b')
        print(sub_net_bits)
        while len(sub_net_bits) < 32:
            sub_net_bits += '0'
        sub_net = ''
        sub_net += str(int(sub_net_bits[0:8], 2))
        sub_net += '.'
        sub_net += str(int(sub_net_bits[8:16], 2))
        sub_net += '.'
        sub_net += str(int(sub_net_bits[16:24], 2))
        sub_net += '.'
        sub_net += str(int(sub_net_bits[24:32], 2))
        net_int += 1

        # Adding to DB
        name = 'AUTO_PREFIX_' + str(current_settings.m_id) + '_' + current_settings.net + '_' + str(i)
        try:
            prefix_list = PrefixLists(name=name, net=sub_net, net_mask=prefix, rm_seq=seq, m_id=current_settings.m_id,
                                      s_id=current_settings.id)
            prefix_list.save()
            response += name + ' создан <br>'
        except IntegrityError as error:
            response += str(error) + ' <br>'

    # All new prefix-lists are associated with all route-maps on current host with prepend = -1 (Do Not Distribute)
    route_maps = RouteMaps.objects.filter(m_id=current_settings.m_id)
    prefixes = PrefixLists.objects.filter(s_id=current_settings.id)
    for route_map in route_maps:
        for prefix in prefixes:
            try:
                rm_to_pl = RMtoPL(rm_id=route_map.id, pl_id=prefix.id, prepend=-1)
                rm_to_pl.save()
                response += prefix.name + ' assigned to ' + route_map.name + '<br>'
            except (IntegrityError, AttributeError) as error:
                response += str(error) + ' <br>'

    # Full prefix prepend set to 0
    for route_map in route_maps:
        try:
            rm_to_pl = RMtoPL.objects.get(rm_id=route_map.id, pl_id=prefix_list_full.id)
            rm_to_pl.prepend = 0
            rm_to_pl.save()
            response += prefix_list_full.name + ' prenend changed to ' + str(rm_to_pl.prepend) + '<br>'
        except (IntegrityError, AttributeError) as error:
            response += str(error) + ' <br>'

    return "<br><br> Создаем Prefix-List'ы в БД: <br>" + response


# Deleting prefix-lists and associations from DB
def prefix_delete(settings_id):
    response = ''
    prefixes_to_delete = PrefixLists.objects.filter(s_id=settings_id)  # Selected prefix-lists
    for prefix in prefixes_to_delete:
        rm_to_pl_list = RMtoPL.objects.filter(pl_id=prefix.id)  # All associations between prefix-lists and route-maps
        for rm_to_pl in rm_to_pl_list:
            try:
                rm = RouteMaps.objects.get(id=rm_to_pl.rm_id)
                rm_to_pl.delete()
                response += 'Assign ' + prefix.name + ' to ' + rm.name + ' deleted <br>'
            except IntegrityError as error:
                response += str(error) + ' <br>'
        try:
            name = prefix.name
            prefix.delete()
            response += name + ' deleted <br>'
        except IntegrityError as error:
            response += str(error) + ' <br>'
    return "Удаляем Prefix-List'ы из БД: <br>" + response


# Loading prefix-lists from settings data to Quagga via Telnet
def prefix_load_to_quagga(settings_id):
    tn = tn_connect()

    current_settings = Settings.objects.get(id=settings_id)
    current_machine = Machines.objects.get(id=current_settings.m_id)
    prefixes_to_load = PrefixLists.objects.filter(s_id=settings_id)

    # Every subnet is used as network for BGP distribution, and added to single prefix-list which is included to the
    # route-map for the selected host with specific sequence number. So different settings can have different nexthops.
    cmd = 'router bgp ' + local_as + '\n'
    for prefix in prefixes_to_load:
        cmd += ' network ' + prefix.net + '/' + str(prefix.net_mask) + '\n'
    cmd += 'exit\n'
    for prefix in prefixes_to_load:
        cmd += 'ip prefix-list AUTO-TO-' + current_machine.ip_address + '_' + str(current_settings.id) + ' seq ' \
               + str(prefix.rm_seq) + ' permit ' + prefix.net + '/' + str(prefix.net_mask) + '\n'
    cmd += 'route-map AUTO-TO-' + current_machine.ip_address + ' permit ' + str(current_settings.quagga_seq) + '\n' \
           ' match ip address prefix-list AUTO-TO-' + current_machine.ip_address + '_' + str(current_settings.id) + '\n'
    if current_settings.nexthop:
        cmd += ' set ip next-hop ' + current_settings.nexthop + '\n' \
               ' exit\n' \
               'route-map AUTO-TO-' + current_machine.ip_address + ' permit 65535\n' \
               ' set ip next-hop ' + current_settings.nexthop + '\n'
    cmd += 'end\n' \
           'wr\n'\
           'clear ip bgp * soft out\n'

    tn_send(tn, cmd)

    output = tn.read_until(b"clear ip bgp * soft out")
    output = output.replace(b'\r\n', b'<br>').decode('utf-8')
    return "Создаем на QUAGGA Prefix-List'ы и их анонсы: <br>" + output


# Deleting prefix-lists from Quagga
def prefix_delete_from_quagga(settings_id):
    tn = tn_connect()

    cmd1 = 'router bgp ' + local_as + '\n'
    cmd2 = ''

    current_settings = Settings.objects.get(id=settings_id)
    current_machine = Machines.objects.get(id=current_settings.m_id)
    prefixes_to_delete = PrefixLists.objects.filter(s_id=settings_id)

    # For every selected IP deletes BGp distribution and prefix-list. Then route-map sequence is deleted
    for prefix in prefixes_to_delete:
        cmd1 += 'no network ' + prefix.net + '/' + str(prefix.net_mask) + '\n'
        cmd2 += 'no ip prefix-list AUTO-TO-' + current_machine.ip_address + '_' + str(current_settings.id) + ' seq ' \
                + str(prefix.rm_seq) + ' permit ' + prefix.net + '/' + str(prefix.net_mask) + '\n'

    cmd1 += 'exit\n'
    cmd = cmd1 + cmd2
    cmd += 'no route-map AUTO-TO-' + current_machine.ip_address + ' permit ' + str(current_settings.quagga_seq) + '\n' \
           'end\n' \
           'wr\n' \
           'clear ip bgp * soft out\n'

    tn_send(tn, cmd)

    output = tn.read_until(b"clear ip bgp * soft out")
    output = output.replace(b'\r\n', b'<br>').decode('utf-8')
    print(output)
    return "Удаляем с QUAGGA Prefix-List'ы и их анонсы: <br>" + output


# Loading prefix-lists to host
def prefix_load_to_host(settings_id):
    current_settings = Settings.objects.get(id=settings_id)
    prefixes_to_load = PrefixLists.objects.filter(s_id=settings_id)
    output = "Создаем Prefix-List'ы на хосте: <br>"

    output_tmp, client, shell, tn = ssh_or_tn(current_settings.m_id)  # SSH or Telnet
    output += output_tmp

    # Creating prefix-lists on host from settings ID
    cmd = 'conf t\n'
    for prefix in prefixes_to_load:
        cmd += 'ip prefix-list ' + prefix.name + ' seq 5 permit ' + prefix.net + '/' + str(prefix.net_mask) + '\n'
    cmd += 'end\n'
    cmd += 'wr\n'

    # SSH
    if not tn and client and shell:
        ssh_send(shell, cmd)
        tmp = shell.recv(4096)
        while tmp.lower().find(b'[ok]') == -1:
            tmp += shell.recv(4096)
        client.close()
        output += tmp.decode('utf-8')

    # Telnet
    elif tn and not client and not shell:
        tn_send(tn, cmd)
        output += tn.read_until(b'[OK]').decode('utf-8')
        tn.close()

    output += prefix_assign_settings(settings_id, 'settings')
    output = output.replace('\r\n', '<br>')
    print(output)
    return output


# Deleting prefixes from host
def prefix_delete_from_host(settings_id):
    current_settings = Settings.objects.get(id=settings_id)
    prefixes_to_delete = PrefixLists.objects.filter(s_id=settings_id)
    output = "Удаляем Prefix-List'ы с хоста: <br>"

    # For selected prefix-lists set prepend = -1
    for prefix in prefixes_to_delete:
        rm_to_pl_list = RMtoPL.objects.filter(pl_id=prefix.id)
        for rm_to_pl in rm_to_pl_list:
            rm_to_pl.prepend = -1
            rm_to_pl.save()

    output += prefix_assign_settings(settings_id, 'settings')

    output_tmp, client, shell, tn = ssh_or_tn(current_settings.m_id)  # SSH ot Telnet
    output += output_tmp

    # Delete
    cmd = 'conf t\n'
    for prefix in prefixes_to_delete:
        cmd += 'no ip prefix-list ' + prefix.name + ' seq 5 permit ' + prefix.net + '/' + str(prefix.net_mask) + '\n'
    cmd += 'end\n'
    cmd += 'wr\n'

    # SSH
    if not tn and client and shell:
        ssh_send(shell, cmd)
        tmp = shell.recv(4096)
        while tmp.lower().find(b'[ok]') == -1:
            tmp += shell.recv(4096)
            print(tmp.decode('utf-8'))
        client.close()
        output += tmp.decode('utf-8')
        print(output)

    # Telnet
    elif tn and not client and not shell:
        tn_send(tn, cmd)
        output += tn.read_until(b'[OK]').decode('utf-8')
        tn.close()
        print(output)

    output = output.replace('\r\n', '<br>')
    print(output)
    return output


# Applying prepends to prefix-lists. Can be assigned by settings id or route-map id
def prefix_assign_settings(input_id, type):
    # Getting all associations between route-map and prefix-lists using settings_id
    if type == 'settings':
        current_settings = Settings.objects.get(id=input_id)
        current_machine = Machines.objects.get(id=current_settings.m_id)
        current_prefix_lists = PrefixLists.objects.filter(s_id=current_settings.id)
        try:
            rm_to_pl_list = RMtoPL.objects.filter(pl_id=current_prefix_lists[0].id)
            for prefix in current_prefix_lists:
                tmp = RMtoPL.objects.filter(pl_id=prefix.id)
                rm_to_pl_list.union(tmp).order_by('id')
        except IndexError:
            rm_to_pl_list = []

    # Getting all associations between route-map and prefix-lists using route-map_id
    elif type == 'rm':
        rm_to_pl_list = RMtoPL.objects.filter(rm_id=input_id)
        current_route_map = RouteMaps.objects.get(id=input_id)
        current_machine = Machines.objects.get(id=current_route_map.m_id)

    output = "Синхронизируем конфигурации Prefix-List'ов и Route-Map'ов:<br>"

    output_tmp, client, shell, tn = ssh_or_tn(current_machine.id)  # SSH or Telnet
    output += output_tmp
    cmd = 'conf t\n'
    for rm_to_pl in rm_to_pl_list:
        current_prefix_list = PrefixLists.objects.get(id=rm_to_pl.pl_id)
        current_route_map = RouteMaps.objects.get(id=rm_to_pl.rm_id)

        # If prepend = -1, then delete route-map sequence
        if rm_to_pl.prepend == -1:
            cmd += 'no route-map ' + current_route_map.name + ' permit ' + str(current_prefix_list.rm_seq) + '\n'
        # Otherwise set route-map sequence matching prefix-list, and set prepend
        else:
            full_prepend = (str(current_machine.remote_as) + ' ') * rm_to_pl.prepend
            cmd += 'route-map ' + current_route_map.name + ' permit ' + str(current_prefix_list.rm_seq) + '\n' \
                   ' match ip address prefix-list ' + current_prefix_list.name + '\n'
            if full_prepend:
                cmd += ' set as-path prepend ' + full_prepend + '\n'
            else:
                cmd += ' no set as-path prepend ' + str(current_machine.remote_as) + '\n'
    cmd += 'end\n'
    cmd += 'wr\n'
    cmd += 'clear ip bgp * soft out\n'

    # SSH
    if not tn and client and shell:
        ssh_send(shell, cmd)
        tmp = shell.recv(4096)
        while tmp.lower().find(b'clear ip bgp * soft out') == -1:
            tmp += shell.recv(4096)
        client.close()
        output += tmp.decode('utf-8')

    # Telnet
    elif tn and not client and not shell:
        tn_send(tn, cmd)
        output += tn.read_until(b'clear ip bgp * soft out').decode('utf-8')
        tn.close()

    output = output.replace('\r\n', '<br>')
    return output


# Setting BlackHole Community on host
def host_set_community(route_map_id):
    current_route_map = RouteMaps.objects.get(id=route_map_id)

    output = "Установка community:<br>"

    # Connect data
    output_tmp, client, shell, tn = ssh_or_tn(current_route_map.m_id)
    output += output_tmp

    # Blackholed IPs matched by local community and thep marked by provider community (different for route-maps)
    cmd = 'conf t\n'
    cmd += 'no ip community-list standard AUTO\n'
    cmd += 'ip community-list standard AUTO permit ' + bgpd_do_not_distribute_community + '\n'
    if current_route_map.community:
        cmd += 'route-map ' + current_route_map.name + ' permit 65535\n' \
                                                       ' match community AUTO \n' \
                                                       ' set community none\n' \
                                                       ' set community ' + str(current_route_map.community) + '\n'
    else:
        cmd += 'no route-map ' + current_route_map.name + ' permit 65535\n'
    cmd += 'end\n'
    cmd += 'wr\n'
    cmd += 'clear ip bgp * soft out\n'

    # SSH
    if not tn and client and shell:
        ssh_send(shell, cmd)
        tmp = shell.recv(4096)
        while tmp.lower().find(b'clear ip bgp * soft out') == -1:
            tmp += shell.recv(4096)
        client.close()
        output += tmp.decode('utf-8')

    # Telnet
    elif tn and not client and not shell:
        tn_send(tn, cmd)
        output += tn.read_until(b'clear ip bgp * soft out').decode('utf-8')
        tn.close()

    output = output.replace('\r\n', '<br>')
    return output
