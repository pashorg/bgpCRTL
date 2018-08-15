from django.shortcuts import get_object_or_404, render
from datetime import datetime, timedelta
from facer.models import Machines, Interfaces, Stats
from .fusioncharts import FusionCharts
from collections import OrderedDict


# Home Page with hosts graphs
def index(request):
    # Getting list of all hosts and setting main variable
    machine_list = Machines.objects.all()
    full_information = {}
    counter_max = 2**32

    # For every host needed data is selected from DB
    for machine in machine_list:
        full_information[machine.id] = {}
        full_information[machine.id]['id'] = machine.id
        full_information[machine.id]['ip_address'] = machine.ip_address
        full_information[machine.id]['description'] = machine.description
        shown_interfaces = Interfaces.objects.filter(m_id=machine.id, enable=1)
        full_information[machine.id]['interfaces'] = {}
        if not shown_interfaces:
            full_information[machine.id]['error'] = 'Не выбраны интерфейсы для мониторинга!'
        # For every int enabled for monitoring creating graph
        for interface in shown_interfaces:
            # Load traffic data for graphs for last 3 hours
            all_stats = Stats.objects.filter(i_id=interface.id,
                                             timestamp__gte=datetime.now() -
                                                            timedelta(hours=3)).order_by('timestamp')

            if all_stats:
                x_end = all_stats[len(all_stats) - 1].timestamp # Current time
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
                        #"xaxisminvalue": "-180",
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

                chart = FusionCharts("scatter", interface.name + str(machine.id) + "ex1", "100%", "400",
                                     interface.name + str(machine.id), "json", chart_data)
                full_information[machine.id]['interfaces'][interface.name + str(machine.id)] = chart.render()

            else:
                full_information[machine.id]['interfaces'][interface.name + str(machine.id)] = 'no data for last 30 min'

    # Order dict
    full_information_sorted = OrderedDict(sorted(full_information.items()))
    return render(request, 'facer/index.html',
                  {
                      "machine_list": machine_list,
                      "data": full_information_sorted,
                  }
                  )












