from django.shortcuts import render
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from .prefix_func import *


# Adding new route-maps to DB
@login_required
def route_map_add(request, machines_id):
    machine_list = Machines.objects.all()
    this_machine = Machines.objects.get(id=machines_id)
    route_map_list = RouteMaps.objects.filter(m_id=machines_id)

    # Adding new route-map to DB
    if request.POST.get('submit', False):
        try:
            name = request.POST.get('name', False)
            route_map = RouteMaps(m_id=machines_id, name=name)
            route_map.save()
            response = name + ' добавлен<br>'

            # Also all new route map is assosiated with all prefix-list no host.
            # Prepend = -1, which is equal to "do not # distribute"
            prefix_lists = PrefixLists.objects.filter(m_id=machines_id)
            for prefix_list in prefix_lists:
                rm_to_pl = RMtoPL(rm_id=route_map.id, pl_id=prefix_list.id, prepend=-1)
                rm_to_pl.save()
                response += prefix_list.name + ' ассоциирован с ' + name + ', prepend -1<br>'

            return render(request, 'facer/route_map_add.html',
                          {
                              "error": response,
                              "route_map_list": route_map_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

        # If error during inserting
        except IntegrityError as error:
            return render(request, 'facer/route_map_add.html',
                          {
                              'error': error,
                              "error_id": 2,
                              "name": name,
                              "route_map_list": route_map_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

    # Deleting route-map
    elif request.POST.get('delete', False):
        try:
            # All prefix-lists, associated with selected route-map, get prepend = -1
            route_map = RouteMaps.objects.get(id=request.POST.get('id', False))
            response = ''
            rm_to_pl_list = RMtoPL.objects.filter(rm_id=route_map.id)
            for rm_to_pl in rm_to_pl_list:
                rm_to_pl.prepend = -1
                rm_to_pl.save()
                response += route_map.name + ', prefix-lists id=' + str(rm_to_pl.pl_id) + ' prepend=-1<br>'
            # Then these settings are applied on host. Then all associations and route-map are deleted
            response += prefix_assign_settings(route_map.id, 'rm')
            for rm_to_pl in rm_to_pl_list:
                response += route_map.name + ', rm_to_pl id=' + str(rm_to_pl.id) + ' удален<br>'
                rm_to_pl.delete()
            route_map.delete()

            return render(request, 'facer/route_map_add.html',
                          {
                              "error": response,
                              "route_map_list": route_map_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )

        # If error during deleting
        except (IntegrityError, RouteMaps.DoesNotExist) as error:
            return render(request, 'facer/route_map_add.html',
                          {
                              'error': error,
                              "error_id": 2,
                              "route_map_list": route_map_list,
                              "machine_list": machine_list,
                              "this_machine": this_machine
                          }
                          )
    else:
        return render(request, 'facer/route_map_add.html',
                      {
                          "machine_list": machine_list,
                          "route_map_list": route_map_list,
                          "this_machine": this_machine
                      }
                      )
