from django.shortcuts import render
from facer.models import Machines, Interfaces
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required


@login_required
# Enabling discovered int for monitoring
def interface_add(request, Machines_id):
    machine_list = Machines.objects.all()
    machine = Machines.objects.get(id=Machines_id)
    interfaces = Interfaces.objects.filter(m_id=machine.id).order_by('snmp_number')

    # Check if interfaces are already discovered
    if not interfaces:
        print('NO INTERFACES')

        return render(request, 'facer/interface_add.html',
                      {
                          "machine_list": machine_list,
                          "this_machine": machine,
                          "interfaces": interfaces,
                          "error": "Нет интерфейсов! Запустите <a href='/interfaces_check/'>проверку интерфейсов</a>"
                      }
                      )

    else:
        # If interface was added then change enabled to 1 in database
        if request.POST.get('submit', False):
            int_id = request.POST.get('id', False)
            max_in = request.POST.get('max_in', False)
            max_out = request.POST.get('max_out', False)

            try:
                interface = Interfaces.objects.get(id=int_id)
                interface.max_in = max_in
                interface.max_out = max_out
                interface.enable = 1
                interface.save()

                interfaces = Interfaces.objects.filter(m_id=machine.id).order_by('snmp_number')

                return render(request, 'facer/interface_add.html',
                              {
                                  "error": "Успешно добавлено!",
                                  "error_id": 200,
                                  "machine_list": machine_list,
                                  "this_machine": machine,
                                  "interfaces": interfaces
                              }
                              )

        # If error during inserting
            except IntegrityError as error:
                return render(request, 'facer/interface_add.html',
                              {
                                  'error': error,
                                  "error_id": 2,
                                  "machine_list": machine_list,
                                  "this_machine": machine,
                                  "interfaces": interfaces
                              }
                              )

        # If interface was deleted then change enabled to 0 in database
        elif request.POST.get('delete', False):
            int_id = request.POST.get('id', False)

            try:
                interface = Interfaces.objects.get(id=int_id)
                interface.max_in = 0
                interface.max_out = 0
                interface.enable = 0
                interface.rm_id = None
                interface.save()

                interfaces = Interfaces.objects.filter(m_id=machine.id)

                return render(request, 'facer/interface_add.html',
                              {
                                  "error": "Успешно удалено!",
                                  "error_id": 200,
                                  "machine_list": machine_list,
                                  "this_machine": machine,
                                  "interfaces": interfaces
                              }
                              )

            # If error during inserting
            except IntegrityError as error:
                return render(request, 'facer/interface_add.html',
                              {
                                  'error': error,
                                  "error_id": 2,
                                  "machine_list": machine_list,
                                  "this_machine": machine,
                                  "interfaces": interfaces
                              }
                              )

        # If refreshed
        else:
            return render(request, 'facer/interface_add.html',
                          {
                              "machine_list": machine_list,
                              "this_machine": machine,
                              "interfaces": interfaces
                          }
                          )
