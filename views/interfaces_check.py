from django.shortcuts import render
from facer.models import Machines, Interfaces
from django.db import IntegrityError
import paramiko
import telnetlib
import re


# Adding known host interfaces to DB
def interfaces_check(request):
    final_response = {}
    all_machines = Machines.objects.all()

    # Checking on all machines
    for machine in all_machines:
        tmp_int = []
        tmp_descr = []
        tmp_ip = []
        tmp_snmp = []
        final_response[machine.ip_address] = {}
        # Check if already has some interfaces
        try:
            current_interfaces = Interfaces.objects.filter(m_id=machine.id)
        except Interfaces.DoesNotExist:
            print("No cur Int for " + machine.ip_address)

        # Connect data
        host = machine.ip_address
        user = machine.login
        secret = machine.password
        port = 22
        enable = machine.enable_password

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, username=user, password=secret, port=port, timeout=15)
            ssh = 1

        except (TimeoutError, paramiko.AuthenticationException, ConnectionRefusedError,
                Exception) as error:
            final_response[machine.ip_address]['SSH Error'] = {}
            final_response[machine.ip_address]['SSH Error']['status'] = error
            final_response[machine.ip_address]['Action'] = {}
            final_response[machine.ip_address]['Action']['status'] = 'Try Telnet'
            try:
                final_response[machine.ip_address]['Telnet Error'] = {}
                tn = telnetlib.Telnet(host, 23)
                tn.read_until(b"Username: ")
                tn.write(user.encode('ascii') + b"\n")
                tn.read_until(b"Password: ")
                tn.write(secret.encode('ascii') + b"\r\n")
                tn.read_until(b">")
                ssh = 0
                final_response[machine.ip_address]['Telnet Error']['status'] = 'Telnet OK!'

            except (TimeoutError, EOFError, ConnectionRefusedError, Exception) as error:
                final_response[machine.ip_address]['Telnet Error']['status'] = error
                ssh = -1

        # Use SSH
        if ssh == 1:
            shell = client.invoke_shell(height=128)

            # Send enable + passwd
            shell.send("enable\n")
            output = shell.recv(1000).decode("utf-8")
            while output.lower().find('password') == -1:
                output += shell.recv(1000).decode("utf-8")
            shell.send(enable + '\n')

            # Get list of interfaces
            shell.send("sh run | include ^interface\n")
            output = shell.recv(65536).decode("utf-8")
            while output.lower().find('/') == -1:
                output += shell.recv(65536).decode("utf-8")
            output = output.split('\r\n')

            # Select int names
            for el in output:
                tmp = el.split(' ')
                if len(tmp) > 0 and tmp[0] == 'interface':
                    tmp_int.append(tmp[1])

            # Get description and ip for each interface
            for interface in tmp_int:
                shell.send("sh run | section include " + interface + "$\n")
                output = shell.recv(65536).decode("utf-8")
                while output.lower().find('#') == -1:
                    output += shell.recv(65536).decode("utf-8")
                description = re.search('(?<=description ).*', output)
                if description:
                    description = description.group(0)
                    description = description[:-1]
                    tmp_descr.append(description)
                else:
                    tmp_descr.append("None")
                ip = re.search('(?<=ip address )[0-9\.]*', output)
                if ip:
                    ip = ip.group(0)
                    tmp_ip.append(ip)
                else:
                    tmp_ip.append("None")

            # get snmp number for each interface
            for interface in tmp_int:
                shell.send('sh snmp mib ifmib ifindex ' + interface + '\n')
                output = shell.recv(65536).decode("utf-8")
                while output.lower().find('#') == -1:
                    output += shell.recv(65536).decode("utf-8")
                snmp = re.search('(?<=Ifindex = )[0-9]*', output)
                if snmp:
                    snmp=snmp.group(0)
                    tmp_snmp.append(snmp)
                else:
                    tmp_snmp.append(0)

            client.close()

        # Use Telnet
        elif ssh == 0:
            tn.write('enable'.encode('ascii') + b"\n")
            tn.read_until(b"Password: ")
            tn.write(enable.encode('ascii') + b"\n")
            tn.read_until(b"#")

            # Get list of interfaces
            tn.write("sh run | include ^interface\n".encode('ascii'))
            output = tn.read_until(b'#', 2).decode('utf-8')
            while output.find('#') == -1:
                tn.write(" ".encode('ascii'))
                output += tn.read_until(b'#', 2).decode('utf-8')
            output = output.split('\r\n')

            # Select int names
            for el in output:
                tmp = el.split(' ')
                if len(tmp) > 0 and tmp[0] == 'interface':
                    tmp_int.append(tmp[1])

            # Get description and ip for each interface
            for interface in tmp_int:
                cmd = "sh run | section include " + interface + "$\n"
                tn.write(cmd.encode('ascii'))
                output = tn.read_until(b'#', 2).decode('utf-8')
                while output.find('#') == -1:
                    tn.write(" ".encode('ascii'))
                    output += tn.read_until(b'#', 2).decode('utf-8')
                description = re.search('(?<=description ).*', output)
                if description:
                    description = description.group(0)
                    description = description[:-1]
                    tmp_descr.append(description)
                else:
                    tmp_descr.append("None")
                ip = re.search('(?<=ip address )[0-9\.]*', output)
                if ip:
                    ip = ip.group(0)
                    tmp_ip.append(ip)
                else:
                    tmp_ip.append("None")

            # get snmp number for each interface
            for interface in tmp_int:
                cmd = 'sh snmp mib ifmib ifindex ' + interface + '\n'
                tn.write(cmd.encode('ascii'))
                output = tn.read_until(b'#', 2).decode('utf-8')
                while output.find('#') == -1:
                    tn.write(" ".encode('ascii'))
                    output += tn.read_until(b'#', 2).decode('utf-8')
                snmp = re.search('(?<=Ifindex = )[0-9]*', output)
                if snmp:
                    snmp=snmp.group(0)
                    tmp_snmp.append(snmp)
                else:
                    tmp_snmp.append(0)

            tn.close()

        for interface in current_interfaces:
            if interface.name not in tmp_int:
                interface.delete()
                final_response[machine.ip_address][interface.name] = {}
                final_response[machine.ip_address][interface.name]['status'] = 'Удален'

        # If there are no interfaces for that host then just create new
        if not current_interfaces:
            for i in range(len(tmp_int)):
                final_response[machine.ip_address][tmp_int[i]] = {}
                try:
                    new_interface = Interfaces(m_id=machine.id, name=tmp_int[i], description=tmp_descr[i],
                                               ip_address=tmp_ip[i], snmp_number=tmp_snmp[i], max_in=0, max_out=0,
                                               enable=False)
                    new_interface.save()
                    final_response[machine.ip_address][tmp_int[i]]['status'] = 'Создан'

                except IntegrityError as error:
                    final_response[machine.ip_address][tmp_int[i]]['status'] = error

        # Otherwise check every one
        else:
            for i in range(len(tmp_int)):
                final_response[machine.ip_address][tmp_int[i]] = {}
                try:
                    current_interface = Interfaces.objects.get(name=tmp_int[i], ip_address=tmp_ip[i],
                                                               description=tmp_descr[i], snmp_number=tmp_snmp[i],
                                                               m_id=machine.id)
                    final_response[machine.ip_address][tmp_int[i]]['status'] = 'ОК'
                # If error during inserting
                except Interfaces.DoesNotExist:
                    try:
                        current_interface = Interfaces.objects.get(name=tmp_int[i], m_id=machine.id)
                        current_interface.description = tmp_descr[i]
                        current_interface.ip_address = tmp_ip[i]
                        current_interface.snmp_number = tmp_snmp[i]
                        current_interface.save()
                        final_response[machine.ip_address][tmp_int[i]]['status'] = 'Обновлен'

                    except Interfaces.DoesNotExist:
                        try:
                            new_interface = Interfaces(m_id=machine.id, name=tmp_int[i], description=tmp_descr[i],
                                                       ip_address=tmp_ip[i], snmp_number=tmp_snmp[i], max_in=0,
                                                       max_out=0, enable=False)
                            new_interface.save()
                            final_response[machine.ip_address][tmp_int[i]]['status'] = 'Создан'
                        except IntegrityError as error:
                            final_response[machine.ip_address][tmp_int[i]]['status'] = error

    return render(request, 'facer/interfaces_check.html',
                  {
                      'machine_list': all_machines,
                      'final_response': final_response
                  })
