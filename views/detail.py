from django.shortcuts import get_object_or_404, render
from django.db import IntegrityError
from datetime import datetime, timedelta
from facer.models import Machines, Interfaces, Stats, RMtoPL, RouteMaps, PrefixLists, Settings
from .fusioncharts import FusionCharts
from .prefix_func import prefix_assign_settings, host_set_community
from django.contrib.auth.decorators import login_required
from collections import OrderedDict


# Main page for host
@login_required
def detail(request, Machines_id):
    # Getting current host info and setting variables
    machine = get_object_or_404(Machines, pk=Machines_id)
    machine_list = Machines.objects.all()
    main_response = ''
    full_information = {}
    counter_max = 2**32
    all_route_maps = RouteMaps.objects.filter(m_id=Machines_id)
    change_response = ''
    update_response = ''
    interface_id = ''

    # Update route-map and RTBH community on selected interface
    if request.POST.get('change', False):
        try:
            interface_id = int(request.POST.get('interface_id', False))
            route_map_id = request.POST.get('route_map_id', False)
            community = request.POST.get('community', '')

            # If no community entered then set to 0:0
            if community == '':
                community = '00000:00000'

            # Set new route-map to current Int and new community to selected route-map
            if route_map_id != 'NULL':
                current_interface = Interfaces.objects.get(id=interface_id)
                current_interface.rm_id = route_map_id
                current_interface.save()
                change_response = ''

                current_route_map = RouteMaps.objects.get(id=route_map_id)
                current_route_map.community = community
                current_route_map.save()

                main_response = host_set_community(current_route_map.id)
            else:
                current_interface = Interfaces.objects.get(id=interface_id)
                current_interface.rm_id = None
                current_interface.save()
                change_response = ''

        except (Interfaces.DoesNotExist, IntegrityError) as error:
            change_response = str(error)

    # Update prefix-lists prepends
    if request.POST.get('update', False):
        update_response = ''
        try:
            interface_id = int(request.POST.get('interface_id', False))
            route_map_id = int(request.POST.get('route_map_id', False))
            rm_to_pl_id = request.POST.getlist('rm_to_pl_id[]', False)
            rm_to_pl_prepend = request.POST.getlist('rm_to_pl_prepend[]', False)

            for id, prepend in zip(rm_to_pl_id, rm_to_pl_prepend):
                rm_to_pl = RMtoPL.objects.get(id=id)
                rm_to_pl.prepend = prepend
                rm_to_pl.save()

            update_response = 'Success!'
            main_response += prefix_assign_settings(route_map_id, 'rm')

        except (RMtoPL.DoesNotExist, IntegrityError, ValueError) as error:
            update_response += str(error)

    # Select interfaces enabled to show
    shown_interfaces = Interfaces.objects.filter(m_id=Machines_id, enable=1)
    if not shown_interfaces:
        main_response += 'No active interfaces'
    for interface in shown_interfaces:
        # Create data dict for every int
        full_information[interface.name] = {}
        full_information[interface.name]['id'] = interface.id
        response = ''

        # Show change and update responses if they appeared
        if interface.id == interface_id:
            response += change_response + '<br>' + update_response + '<br>'

        # Route-map data
        try:
            current_route_map = RouteMaps.objects.get(id=interface.rm_id)
            full_information[interface.name]['route_map'] = {}
            full_information[interface.name]['route_map']['name'] = current_route_map.name
            full_information[interface.name]['route_map']['id'] = current_route_map.id
            full_information[interface.name]['route_map']['community'] = current_route_map.community
        except RouteMaps.DoesNotExist as error:
            full_information[interface.name]['route_map'] = {}
            full_information[interface.name]['route_map']['name'] = 'No active Route-Map'
            current_route_map = None
            response += str(error)

        # If route-map is selected exclude it from list of all route-maps (to prevent duplicates on different
        # interfaces) and load data about prefix-lists
        if current_route_map:
            all_route_maps.exclude(id=current_route_map.id)
            full_information[interface.name]['prefix_lists'] = {}
            rm_to_pl_list = RMtoPL.objects.filter(rm_id=current_route_map.id)
            for rm_to_pl in rm_to_pl_list:
                prefix_list = PrefixLists.objects.get(id=rm_to_pl.pl_id)
                full_information[interface.name]['prefix_lists'][rm_to_pl.id] = {}
                full_information[interface.name]['prefix_lists'][rm_to_pl.id]['id'] = rm_to_pl.id
                full_information[interface.name]['prefix_lists'][rm_to_pl.id]['net'] = prefix_list.net + '/' + \
                                                                                       str(prefix_list.net_mask)
                full_information[interface.name]['prefix_lists'][rm_to_pl.id]['prepend'] = rm_to_pl.prepend
                current_setings = Settings.objects.get(id=prefix_list.s_id)
                full_information[interface.name]['prefix_lists'][rm_to_pl.id]['max_prepend'] = \
                    current_setings.max_prepend

        # Load traffic data for graphs for last 3 hours
        all_stats = Stats.objects.filter(i_id=interface.id,
                                         timestamp__gte=datetime.now() -
                                                        timedelta(hours=3)).order_by('timestamp')
        if all_stats:
            x_end = all_stats[len(all_stats) - 1].timestamp  # Current time

            # Counters arrays
            data_in = []
            data_out = []
            for i in range(1, len(all_stats)):
                # Time back from now in seconds converted to minutes
                x = all_stats[i].timestamp - x_end
                x = x.total_seconds()
                x /= 60

                # Timedelta between two dots
                time2 = all_stats[i].timestamp
                time1 = all_stats[i-1].timestamp
                dtime = time2 - time1
                dtime = dtime.total_seconds()

                # Counting channel load in Bps
                if all_stats[i].counter_in < all_stats[i - 1].counter_in:
                    y_in = (counter_max - all_stats[i - 1].counter_in + all_stats[i].counter_in) / dtime
                else:
                    y_in = (all_stats[i].counter_in - all_stats[i - 1].counter_in) / dtime

                if all_stats[i].counter_out < all_stats[i - 1].counter_out:
                    y_out = (counter_max - all_stats[i - 1].counter_out + all_stats[i].counter_out) / dtime
                else:
                    y_out = (all_stats[i].counter_out - all_stats[i - 1].counter_out) / dtime

                # Append to arrays in Mbps
                data_in.append({
                    "y": y_in * 8 / 1024 / 1024,
                    "x": x
                })
                data_out.append({
                    "y": y_out * 8 / 1024 / 1024,
                    "x": x
                })

            # Create charts via fusionchart
            chart_data = {
                "chart": {
                    "palette": "2",
                    "caption": interface.description,
                    "yaxisname": "Speed (Mbps)",
                    "xaxisname": "Time (Minutes)",
                    "xaxismaxvalue": "0",
                    "xaxisminvalue": "180",
                    "yaxismaxvalue": "200"
                },
                "dataset": [
                    {
                        "drawline": "1",
                        "seriesname": "Out",
                        "color": "0000FF",
                        "anchorsides": "2",
                        "anchorradius": "2",
                        "anchorbgcolor": "C6C6FF",
                        "anchorbordercolor": "0000FF",
                        "data": data_out
                    },
                    {
                        "drawline": "1",
                        "seriesname": "in",
                        "color": "009900",
                        "anchorsides": "2",
                        "anchorradius": "2",
                        "anchorbgcolor": "D5FFD5",
                        "anchorbordercolor": "009900",
                        "data": data_in
                    }
                ],
                "trendlines": [
                    {
                        "line": [
                            {
                                "startvalue": interface.max_out,
                                "displayvalue": str(interface.max_out) + 'Mbps',
                                "linethickness": "2",
                                "color": "0000FF",
                                "valueonright": "1",
                                "dashed": "1",
                                "dashgap": "5"
                            },
                            {
                                "startvalue": interface.max_in,
                                "displayvalue": str(interface.max_in) + 'Mbps',
                                "linethickness": "2",
                                "color": "009900",
                                "valueonright": "1",
                                "dashed": "1",
                                "dashgap": "5"
                            }
                        ]
                    }
                ]
            }

            chart = FusionCharts("zoomscatter", interface.name + "ex1", "100%", "400", interface.name, "json", chart_data)
            full_information[interface.name]['chart'] = chart.render()
            full_information[interface.name]['response'] = response

    # Order dict
    full_information_sorted = OrderedDict(sorted(full_information.items()))
    return render(request, 'facer/detail.html',
                  {
                      "main_response": main_response,
                      "this_machine": machine,
                      "machine_list": machine_list,
                      "data": full_information_sorted,
                      "all_route_maps": all_route_maps
                  }
                  )












