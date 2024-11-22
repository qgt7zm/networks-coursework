import math

import simtime


class AccessPoint():
    '''
    Main controller of the network that collects packets from each station.
    '''

    NOISE_FLOOR = -91.3
    MINIMUM_SNR_AP = 20.0
    MINIMUM_SNR_CCA = 4.0

    def __init__(self, recv_queue, station_queues, station_locations, pkts_to_receive=100, time_limit=None):
        # Save the queues we use to talk to the stations.
        self.recv_queue = recv_queue
        self.station_queues = station_queues

        # Save the locations of all of the stations so we can calculate the
        # distance.
        self.station_locations = station_locations

        # Save configuration about how the network should work.
        self.pkts_to_receive = pkts_to_receive

        # Save configured time limit
        self.time_limit = time_limit

        # Keep track of what each station is doing, how many packets we
        # have received from each station, and, if needed, which station has
        # control of the wireless channel.
        self.active = []
        self.pkts_received = []
        for i in range(len(station_queues)):
            self.active.append({'tx': None, 'corrupted': False, 'packet': 0, 'tx_power': 0.0, 'channel': 0})
            self.pkts_received.append([])
        self.cts_node = None


    def run(self):
        # Loop until we have enough packets from each station.
        while True:
            # Wait until we have a "packet" to receive from some station.
            # Note: packets are actually two queue messages: a START and a DONE
            # message.
            msg = self.recv_queue.get()

            # print('AP: {} sent {}({})'.format(msg['id'], msg['type'], msg['mod']))

            # Handle each message appropriately.
            if msg['type'] == 'SENSE':
                # Determine if the node should be able to hear messages
                # from other nodes.
                active = self._check_for_tx(msg['id'], msg['channel'])
                if active:
                    self._send_to_station(msg['id'], 'channel_active')
                else:
                    self._send_to_station(msg['id'], 'channel_inactive')

            elif msg['type'] == 'DATA':

                if msg['mod'] == 'START':
                    # Mark that this node is transmitting
                    self.active[msg['id']]['tx'] = 'DATA'
                    self.active[msg['id']]['tx_power'] = msg['tx_power']
                    self.active[msg['id']]['channel'] = msg['channel']
                    self.active[msg['id']]['packet'] = msg['packet']
                    # Check if any other transmissions should be corrupted
                    self._check_for_collisions(msg['id'])

                elif msg['mod'] == 'DONE':
                    # for i,station in enumerate(self.active):
                    #   print('{}: t:{} c:{};  '.format(i, station['tx'], station['corrupted']), end='')
                    # print('')

                    # Ok the packet is done being sent. If it isn't corrupted
                    # and we received it then we ack.
                    if self.active[msg['id']]['corrupted'] == False:
                        self.pkts_received[msg['id']].append(self.active[msg['id']]['packet'])
                        self.active[msg['id']]['tx'] = None
                        self._send_to_station(msg['id'], 'ACK')
                        print('AP: Got packet #{} from station id:{}'.format(self.active[msg['id']]['packet'], msg['id']))
                    else:
                        # Packet was corrupted, nothing we can do.
                        self.active[msg['id']]['tx'] = None
                        self.active[msg['id']]['corrupted'] = False
                        self._send_to_station(msg['id'], 'NOACK')

                        # print('AP: Data packet from {} was corrupted'.format(msg['id']))


            # Check if we are all done (we have received enough packets from
            # each node).
            received_all = True
            for i,station_packets in enumerate(self.pkts_received):
                if len(station_packets) < self.pkts_to_receive:
                    received_all = False
                    break
                else:
                    pass
                    # print('received {} packets from station {}'.format(len(station_packets), i))
            if received_all:
                # print(self.pkts_received)
                break
            if self.time_limit != None and simtime.time() > self.time_limit:
                break


    ##
    ## Internal Functions
    ##

    def _check_for_collisions(self, id):
        channel = self.active[id]['channel']

        # Check for every transmitter (i) if they should be marked corrupted
        for i,tx in enumerate(self.active):

            # We only care if the node is transmitting and isn't already
            # corrupted and is using the same channel
            if tx['tx'] == None or \
               tx['corrupted'] == True or \
               tx['channel'] != channel:
                continue

            # Now determine the noise floor with all other nodes transmitting
            noise_interference_w = 10**(self.NOISE_FLOOR / 10.0)
            for j,tx2 in enumerate(self.active):
                if j == i:
                    # Don't interfere yourself
                    continue

                if tx2['tx'] == None or tx2['channel'] != channel:
                    # Ignore things not transmitting or on different channel
                    continue


                tx2_distance = self._distance_to_ap(j)
                path_loss = self._calculate_path_loss(tx2_distance)
                rx_signal = tx2['tx_power'] - path_loss
                rx_signal_w = 10**(rx_signal / 10.0)
                noise_interference_w += rx_signal_w

            # print('noise floor during TX is {}'.format(noise_interference_w))
            noise_interference = 10*math.log10(noise_interference_w)

            # Now check if packet is corrupted
            tx_distance = self._distance_to_ap(i)
            path_loss = self._calculate_path_loss(tx_distance)
            snr = tx['tx_power'] - path_loss - noise_interference

            # print('tx distance: {}, path_loss: {}, snr: {}'.format(tx_distance, path_loss, snr))

            # If SNR too low, this packet is corrupted.
            if snr < self.MINIMUM_SNR_AP:
                # print('Corrupted or unable to receive from {}'.format(i))
                tx['corrupted'] = True


    def _send_to_station(self, id, msg):
        self.station_queues[id].put(msg)

    def _distance_between(self, a, b):
        x1 = self.station_locations[a][0]
        y1 = self.station_locations[a][1]
        x2 = self.station_locations[b][0]
        y2 = self.station_locations[b][1]
        return self._calculate_distance(x1, y1, x2, y2)

    def _distance_to_ap(self, a):
        x1 = self.station_locations[a][0]
        y1 = self.station_locations[a][1]
        return self._calculate_distance(x1, y1, 0, 0)

    def _check_for_tx(self, id, channel):

        # Calculate noise at receiver
        noise_interference_w = 10**(self.NOISE_FLOOR / 10.0)
        for i,tx in enumerate(self.active):
            if i == id:
                continue

            if tx['tx'] == None or tx['channel'] != channel:
                # Ignore things not transmitting or on different channel
                continue

            distance = self._distance_between(id, i)
            path_loss = self._calculate_path_loss(distance)
            rx_signal = tx['tx_power'] - path_loss
            rx_signal_w = 10**(rx_signal / 10.0)

            noise_interference_w += rx_signal_w

        noise = 10*math.log10(noise_interference_w)
        snr = noise - self.NOISE_FLOOR

        if snr >= self.MINIMUM_SNR_CCA:
            return True

        return False

    def _calculate_distance(self, x1, y1, x2, y2):
        return math.sqrt(((x2-x1)**2)+((y2-y1)**2))

    def _calculate_path_loss(self, d_meters):
        return (20*math.log10(d_meters)) + (20*math.log10(2400000000)) - 147.55


