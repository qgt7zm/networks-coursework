import random
import threading
import simtime
import queue

class Station(threading.Thread):
    '''
    Base class for implementing a wireless station (transmitter).
    '''

    def __init__(self, id, q_to_ap, q_to_station, pkts_p_sec, *args, **kwargs):
        self.id = id
        self.q_to_ap = q_to_ap
        self.q_to_station = q_to_station
        self.interval = 1.0/pkts_p_sec
        self.last_tx = None
        self.seq_no = 0

        print('Setting up station id:{}'.format(id))

        super().__init__(*args, **kwargs)

    def wait_for_next_transmission(self):
        '''
        Blocks until this station is ready to send another packet to the
        access point.
        '''

        # If we have already sent one packet
        if self.last_tx != None:
            # Check if we have waited long enough
            now = simtime.time()
            diff = now - self.last_tx
            if self.interval > diff:
                # Calculate how much more to wait, and add some randomness
                # while keeping the average interval the same
                to_wait = self.interval - diff
                to_wait += ((random.random() - 0.5) * (0.2*to_wait))
                # print('waiting... {}s'.format(to_wait))
                simtime.sleep(to_wait)

        self.last_tx = simtime.time()

        pkt = self.seq_no
        self.seq_no += 1
        return pkt

    def send(self, packet, tx_power, channel):
        '''
        Send a packet to the access point.

        You must set the tx_power in dB (max 20), and the channel (1-11).
        '''

        if tx_power > 20.0:
            return 'invalid tx power'
        if int(channel) != channel or channel < 1 or channel > 11:
            return 'invalid channel'

        self._send_to_access_point('DATA', 'START', packet, tx_power, channel)
        simtime.sleep(0.01) # 10 millisecond transmission time
        self._send_to_access_point('DATA', 'DONE')

        # Check if we got an ack
        msg = self.q_to_station.get()
        if msg == 'ACK':
            return 'ACK'
        elif msg == 'NOACK':
            return 'NOACK'
        else:
            print('Error this is bad!!')
            return None

    def sense(self, channel):
        '''
        Returns True if the wireless channel is occupied, false otherwise.
        '''

        if int(channel) != channel or channel < 1 or channel > 11:
            return 'invalid channel'

        self._send_to_access_point('SENSE', '', 0, 0.0, channel)
        msg = self.q_to_station.get()
        if msg == 'channel_active':
            return True
        elif msg == 'channel_inactive':
            return False
        else:
            print('Huh?? Should not receive some other packet in sense.')
            return None


    # Internal function, do not call from mac.py.
    def _send_to_access_point(self, type, modifier='', packet=0, tx_power=0.0, channel=1):
        to_send = {
            'id': self.id,
            'type': type,
            'mod': modifier,
            'packet': packet,
            'tx_power': tx_power,
            'channel': channel,
        }
        self.q_to_ap.put(to_send)

