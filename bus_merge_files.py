import pandas as pd

stop_times = pd.read_csv("ttdata/stop_times.txt")
routes = pd.read_csv("ttdata/routes.txt")
trips = pd.read_csv("ttdata/trips.txt")
calendar = pd.read_csv("ttdata/calendar.txt", names=['service_id', 'monday', 'tuesday',
                                                   'wednesday', 'thursday', 'friday', 'saturday',
                                                   'sunday', 'start_date', 'end_date'], header=0)

# merge the dfs in order to simplify extraction process
a = pd.merge(stop_times, trips, on=['trip_id'])
b = pd.merge(a, calendar, on=['service_id'])
c = pd.merge(b, routes, on=['route_id'])
c = c.sort_values('arrival_time')
d = c[['stop_id', 'arrival_time','route_short_name','trip_headsign', 'monday', 'tuesday', 'wednesday', 'thursday',
       'friday', 'saturday', 'sunday']]
d.to_csv('ttdata/merged.txt', index=False)