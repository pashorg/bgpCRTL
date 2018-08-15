from django.shortcuts import render
from facer.models import Machines, Settings, PrefixLists
from django.db import IntegrityError
from django.db.models import Max
from .prefix_func import *
import re
from django.contrib.auth.decorators import login_required


@login_required
# Adding new settings (BGP announcements data) to DB
def settings_set(request, Machines_id):
    machine_list = Machines.objects.all()
    this_machine = Machines.objects.get(id=Machines_id)
    settings_list = Settings.objects.filter(m_id=Machines_id)

    if request.POST.get('submit', False):
        try:
            # Getting POST data
            net = request.POST.get('net', False)
            net_mask = request.POST.get('net_mask', False)
            max_prefix = request.POST.get('max_prefix', False)
            max_prepend = request.POST.get('max_prepend', False)
            nexthop = request.POST.get('nexthop', False)

            # Max_prefix should be greater, or equal, otherwise it is not possible to split whole subnet to smaller ones
            if net_mask > max_prefix:
                return render(request, 'facer/settings_set.html',
                              {
                                  "error": 'Маска и/или препенд неверны!',
                                  "error_id": 2,
                                  "settings_list": settings_list,
                                  "machine_list": machine_list,
                                  "this_machine": this_machine,
                                  "net": net,
                                  "net_mask": net_mask,
                                  "max_prefix": max_prefix,
                                  "max_prepend": max_prepend,
                                  "nexthop": nexthop
                              }
                              )

            # Getting maximum quagga_seq - id for different settings in quagga
            if settings_list:
                max_seq = settings_list.aggregate(Max('quagga_seq'))
                max_seq = max_seq['quagga_seq__max']
            else:
                max_seq = 0

            new_settings = Settings(m_id=Machines_id, net=net, net_mask=net_mask, max_prepend=max_prepend,
                                    max_prefix=max_prefix, nexthop=nexthop, quagga_seq=max_seq+1)
            new_settings.save()

            error = "Успешно добавлено! <br><br>"

            settings_list = Settings.objects.filter(m_id=Machines_id)

            # Create prefix-lists from current settings, load then to Quagga and host
            error += prefix_create(new_settings.id) + '<br><br>'
            error += prefix_load_to_quagga(new_settings.id) + '<br><br>'
            error += prefix_load_to_host(new_settings.id)

            return render(request, 'facer/settings_set.html',
                          {
                              "error": error,
                              "error_id": 200,
                              "settings_list": settings_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

        # If error during inserting
        except IntegrityError as error:
            return render(request, 'facer/settings_set.html',
                          {
                              'error': error,
                              "error_id": 2,
                              "settings_list": settings_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

    # Delete selected settings
    elif request.POST.get('delete', False):
        try:
            current_settings = Settings.objects.get(id=request.POST.get('id', False))
            error = prefix_delete_from_host(current_settings.id) + '<br><br>'  # Del prefix-list from host
            error += prefix_delete_from_quagga(current_settings.id) + '<br><br>'  # Del prefix-list from Quagga
            error += prefix_delete(current_settings.id)  # Del prefix-list from DB
            current_settings.delete()  # Del settings from DB

            return render(request, 'facer/settings_set.html',
                          {
                              "error": "Успешно удалено! <br>" + error,
                              "error_id": 200,
                              "settings_list": settings_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

        # If error during deleting
        except IntegrityError as error:
            return render(request, 'facer/settings_set.html',
                          {
                              'error': error,
                              "error_id": 2,
                              "settings_list": settings_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

    else:
        return render(request, 'facer/settings_set.html',
                      {
                          "machine_list": machine_list,
                          "settings_list": settings_list,
                          "this_machine": this_machine
                      }
                      )
