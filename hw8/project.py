#!/usr/bin/env python3

import argparse
import random
import sys

import simtime

import access_point
import mac

parser = argparse.ArgumentParser()
parser.add_argument('number_stations', type=int,
                    help='total number of transmitting stations')
parser.add_argument('packets_per_second', type=float,
                    help='total number of packets generated per second per station')
parser.add_argument('packets_to_receive', type=int,
                    help='total number of packets to receive per station')
parser.add_argument('--mac', type=str, default='NullMac',
                    help='which class in mac.py to use (default: NullMac)')
parser.add_argument('--real-time', action='store_true', default=False,
                    help='make simulation use wallclock time instead of a simulated clock')
parser.add_argument('--stop-at', type=float, help='stop simulation at timestamp regardless of whether complete')
args = parser.parse_args()

NUMBER_STATIONS = args.number_stations
PACKETS_PER_SECOND = args.packets_per_second
PACKETS_TO_RECEIVE = args.packets_to_receive
MAC = args.mac
REAL_TIME = args.real_time

mac_protocol = getattr(mac, args.mac)

if NUMBER_STATIONS < 5:
    goal_time = (PACKETS_TO_RECEIVE / PACKETS_PER_SECOND)
elif NUMBER_STATIONS < 15:
    goal_time = ((PACKETS_TO_RECEIVE / PACKETS_PER_SECOND) * NUMBER_STATIONS) / 5
else:
    goal_time = ((PACKETS_TO_RECEIVE / PACKETS_PER_SECOND) * NUMBER_STATIONS) / 10

print('Running Simulator. Settings:')
print('  Number of stations: {}'.format(NUMBER_STATIONS))
print('  Packets / second:   {}'.format(PACKETS_PER_SECOND))
print('  MAC Protocol:       {}'.format(mac_protocol))
print('  Goal Time:          {}'.format(goal_time))
print('  Timekeeping:        {}'.format('simulated [fast]' if not args.real_time else 'wall-clock'))


# Track the start time of running the simulator.
if args.real_time:
    simtime.set_real_time()
else:
    simtime.set_fake_time()
start = simtime.time()

# Need a queue to simulate wireless transmissions to the access point.
q_to_ap = simtime.Queue()
station_queues = []

# Need to know where each station is.
station_locations = {}

# Setup and start each wireless station.
for i in range(NUMBER_STATIONS):
    # Get random x,y for station.
    x = round((random.randint(1, 500) / 10.0) - 10.0, 1)
    y = round((random.randint(1, 500) / 10.0) - 10.0, 1)
    station_locations[i] = (x, y)

    q = simtime.Queue()
    station_queues.append(q)
    t = mac_protocol(i, q_to_ap, q, PACKETS_PER_SECOND)
    t.daemon = True
    t.start()

    # Delay to space stations
    simtime.sleep((1.0/PACKETS_PER_SECOND) / NUMBER_STATIONS)

print('Setup {} stations:'.format(NUMBER_STATIONS))
for i,location in station_locations.items():
    print('  Station {}: x: {}, y: {}'.format(i, location[0], location[1]))

# And run the access point.
ap = access_point.AccessPoint(q_to_ap, station_queues, station_locations, PACKETS_TO_RECEIVE, args.stop_at)
ap.run()

# When the access point stops running then we have received the correct number
# of packets from each station.
end = simtime.time()

if args.stop_at and end >= args.stop_at:
    print('Exceeded --stop-at time.')
else:
    print('Took {} seconds'.format(end-start))
    print('Goal Time: {} seconds'.format(goal_time))
    sys.exit(0)
