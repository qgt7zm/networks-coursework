import config
import copy
from util import Packet, Message, create_timer, cancel_timer, now, trace, error
from buffer import DropTailBuffer
import util

import argparse
import json
import random
import re
import sys
import math
from collections import deque
from dataclasses import dataclass
from heapq import heappush, heappop
from typing import Optional

@dataclass
class Event:
    time: float
    action: callable
    description: str
    index: int = 0
    canceled: bool = False

    def __lt__(self, other) -> bool:
        if self.time == other.time:
            return self.index < other.index
        else:
            return self.time < other.time

class Link:
    def __init__(self, simulator, buffer_obj, bandwidth, delay, delay_variance, drop, label):
        self._simulator = simulator
        self._bandwidth = bandwidth
        self._buffer = buffer_obj
        self._delay = delay
        self._delay_variance = delay_variance
        self._drop = drop
        self._pending_transmit = None
        self._label = label
        self._total_sent = 0
        self._maximum_buffer = 0
        self._last_buffer_measure_time = 0.0
        self._buffer_time_occ = 0.0
        self._wrong_seq_num = 0

    def get_rng(self):
        return self._simulator.get_rng()

    def _transmit(self, packet):
        if self.get_rng().uniform(0.0, 1.0) > self._drop:
            delay = self._delay
            if self._delay_variance > 0:
                delay += self.get_rng().expovariate(self._delay_variance)
            self._simulator.trace('link', f'sending {packet} on {self._label} link [{delay} transmission time]')
            self._simulator.create_timer(
                delay,
                lambda: packet._hidden_destination.from_network(packet),
                f'receiving {packet} on {self._label} link'
            )
        else:
            self._simulator.trace('link', f'sending {packet} on {self._label} link [randomly dropped]')

    def transmit_next(self):
        packet = self._buffer.dequeue()
        if packet != None:
            self._transmit(packet)
            self._pending_transmit = self._simulator.create_timer(
                1.0 / self._bandwidth,
                lambda: self.transmit_next(),
                f'dequeue from buffer on {self._label} link',
            )
        else:
            self._pending_transmit = None

    def enqueue(self, packet, destination):
        packet = copy.copy(packet)
        self._total_sent += 1
        packet._hidden_destination = destination
        if packet.seq_num != None and packet.seq_num > config.MAXIMUM_SEQUENCE:
            error(f'packet had seq_num {packet.seq_num} > MAXIMUM_SEQUENCE = {config.MAXIMUM_SEQUENCE}')
            self._wrong_seq_num += 1
        self._buffer.enqueue(packet)
        try:
            used = self._buffer.get_current_used_count()
            self._maximum_buffer = max(used, self._maximum_buffer)
            time_delta = now() - self._last_buffer_measure_time
            self._buffer_time_occ += time_delta * used
            self._last_buffer_measure_time = now()
        except AttributeError:
            self._maximum_buffer = -1
        except TypeError:
            self._maximum_buffer = -1
        if self._pending_transmit == None:
            self.transmit_next()

    def json_info(self):
        return {
            'label': self._label,
            'total_dropped': getattr(self._buffer, '_drop_count', -1),
            'total_sent': self._total_sent,
            'buffer_size': getattr(self._buffer, '_capacity', -1),
            'maximum_buffer_used': self._maximum_buffer,
            'mean_buffer_used': self._buffer_time_occ / max(1.0, self._last_buffer_measure_time),
            'delay': self._delay,
            'delay_variance': self._delay_variance,
            'drop_rate': self._drop,
            'wrong_seq_num': self._wrong_seq_num,
        }

class Connection:
    def __init__(self, simulator, label, sender, receiver, forward_link, backward_link, missing_is_error):
        self._simulator = simulator
        self._label = label
        self._missing_is_error = missing_is_error
        self._total_sent = 0
        self._total_received = 0
        self._total_received_latency = 0.0
        self._total_received_latency_squared = 0.0
        self._pending_messages = deque()
        self._in_flight_messages = deque()
        self._corrupt_message_count = 0
        self._skip_message_count = 0
        self._sender = sender
        self._sender.ready_for_more_from_application = lambda: self.send_pending()
        self._sender.to_network = lambda packet: self._enqueue_forward(packet)
        self._sender._label = label
        self._receiver = receiver
        self._receiver.to_application = lambda m: self.record_received(m)
        self._receiver.to_network = lambda packet: self._enqueue_backward(packet)
        self._receiver._label = label
        self._start_time = float('inf')
        self._finish_time = None
        self._forward_link = forward_link
        self._backward_link = backward_link
        self._generate_rate = 0
        self._generate_max = 0
        self._generate_count = 0

    """generate messages at an exponentially distributed rate instead of using pending message logic"""
    def generate_messages(self, rate, total_messages):
        self._generate_max = total_messages
        self._generate_rate = rate
        self._generate_next()

    """internal function for generate_messages()"""
    def _generate_next(self)-> None:
        if self._generate_max == None or self._generate_count < self._generate_max:
            self._generate_count += 1
            msg = Message(
                data=f'C{self._label:4s}M{self._generate_count:#015x}',
                is_end=self._generate_count == self._generate_max
            )
            trace('generate-next', f'data = {msg.data}')
            self.send_messages([msg])
            if not msg.is_end:
                create_timer(
                    self._simulator.get_rng().expovariate(self._generate_rate),
                    lambda: self._generate_next(),
                    f'generate message for {self._label} (after {self._generate_count})',
                )

    def _enqueue_forward(self, packet: Packet) -> None:
        packet.label = self._label
        self._forward_link.enqueue(packet, self._receiver)

    def _enqueue_backward(self, packet: Packet) -> None:
        packet.label = self._label
        self._backward_link.enqueue(packet, self._sender)


    def send_messages(self, messages: list[Message]) -> None:
        self._start_time = min(self._start_time, now())
        self._pending_messages.extend(messages)
        self.send_pending()

    def send_pending(self) -> None:
        while len(self._pending_messages) > 0:
            result = self._sender.from_application(self._pending_messages[0])
            if result == None:
                error('from_application() in sender did not return True or False')
            if result:
                message = self._pending_messages.popleft()
                self._total_sent += 1
                trace('conn-sent', f'{self._label}: sent message #{self._total_sent} ({message})')
                self._in_flight_messages.append((now(), message))
            else:
                break

    def record_received(self, actual_message: Message) -> None:
        if len(self._in_flight_messages) == 0:
            self._corrupt_message_count += 1
            error(f'received excess message when none expected')
            return
        timestamp, expect_message = self._in_flight_messages.popleft()
        self._total_received += 1
        if expect_message == actual_message:
            time_delta = now() - timestamp
        else:
            skip = 1
            found = False
            for timestamp, item in self._in_flight_messages:
                if actual_message == item:
                    found = True
                    break
                skip += 1
            if found:
                for _ in range(skip):
                    self._in_flight_messages.popleft()
                if self._missing_is_error:
                    error(f'missing {skip} messages before received message #{self._total_received}')
                self._skip_message_count += skip
                time_delta = now() - timestamp
            else:
                time_delta = None
                if self._missing_is_error:
                    error(f'received message #{self._total_received} corrupted; got {actual_message}, expected {expect_message}')
                self._corrupt_message_count += 1
        if time_delta != None:
            self._total_received_latency += time_delta
            self._total_received_latency_squared += time_delta * time_delta
        trace('link', f'received message #{self._total_received} ({actual_message})')

    def _latency_mean_and_variance(self):
        if self._total_received > 0:
            latency_mean = self._total_received_latency / self._total_received
            latency_variance = (self._total_received_latency_squared / self._total_received) - \
                latency_mean * latency_mean
        else:
            latency_mean = float('nan')
            latency_variance = float('nan')
        return latency_mean, latency_variance

    def print_statistics(self):
        unfinished = (self._finish_time == None)
        if unfinished:
            end_time = now()
        else:
            end_time = self._finish_time
        if self._generate_rate:
            print(f'{self._label}: generated {self._generate_rate:.1f} packets/sec')
        print(f"{self._label}: received {self._total_received} in {end_time - self._start_time:.1f} ({self._total_received / (end_time - self._start_time):.1f} messages/time unit)")
        latency_mean, latency_variance = self._latency_mean_and_variance()
        print(f"{self._label}: latency: mean {latency_mean:.2f} "
              f" +/- sd {math.sqrt(latency_variance):.2f}")
        if len(self._in_flight_messages) > 0 or self._skip_message_count > 0 or \
                self._corrupt_message_count > 0:
            print(f"{self._label}: {self._skip_message_count} messages skipped, {len(self._in_flight_messages)} not received at end, {self._corrupt_message_count} corrupt or received out-of-order")

    def json_info(self):
        unfinished = (self._finish_time == None)
        if unfinished:
            end_time = now()
        else:
            end_time = self._finish_time
        latency_mean, latency_variance = self._latency_mean_and_variance()
        return {
            'generate_rate': self._generate_rate,
            'received': self._total_received,
            'time': end_time - self._start_time,
            'received_rate': self._total_received / (end_time - self._start_time),
            'skipped': self._skip_message_count,
            'corrupt': self._corrupt_message_count,
            'in_flight': len(self._in_flight_messages),
            'latency_mean': latency_mean,
            'latency_sd': math.sqrt(latency_variance),
        }

class Simulator:
    def __init__(self, args):
        self._args = args
        self._rng = random.Random(42)
        self._event_list = []
        self._connections = {}
        self._links = {}
        self._next_index = 0
        self._time = 0.0
        self._in_run_event = False
        self.done = False

    def get_rng(self):
        return self._rng

    def time(self) -> float:
        return self._time

    def add_event(self, event: Event) -> None:
        event.index = self._next_index
        self._next_index += 1
        heappush(self._event_list, event)

    def _pop_event(self) -> Optional[Event]:
        if len(self._event_list) > 0:
            return heappop(self._event_list)
        else:
            return None
 
    def error(self, description):
        if len(config.TRACE) > 0:
            print(f"ERROR: at time={self._time:9.1f}: {description}")
        else:
            print(f"ERROR: at time={self._time:9.1f}: {description}", file=sys.stderr)

    def trace(self, label, description):
        if label in config.TRACE or 'all' in config.TRACE:
            print(f"at time={self._time:9.1f}: [{label}] {description}")

    def new_link(self, label, bandwidth, buffer_size, delay, delay_variance, drop, buffer_cls=DropTailBuffer):
        buffer_obj = buffer_cls(buffer_size, bandwidth, label)
        link = self._links[link._label] = Link(
            simulator=self,
            bandwidth=bandwidth,
            buffer_obj=buffer_obj,
            delay=delay,
            delay_variance=delay_variance,
            drop=drop,
            label=label,
        )
        return link


    def new_connection(self, label, sender, receiver, forward_link_name, backward_link_name,
                       missing_is_error=True):
        result = self._connections[label] = Connection(
            simulator=self,
            label=label,
            sender=sender,
            receiver=receiver,
            forward_link=self._links[forward_link_name],
            backward_link=self._links[backward_link_name],
            missing_is_error=missing_is_error,
        )
        result._generate_next()
        return result

    def _run_next(self) -> bool:
        assert not self._in_run_event
        event = self._pop_event()
        if event != None:
            self._time = max(self._time, event.time)
            if not event.canceled:
                self._in_run_event = True
                trace('events', f"running {event.description}")
                event.action()
                self._in_run_event = False
            return True
        else:
            return False

    def run(self, time_limit=None):
        assert util._simulator == self
        while not self.done and self._run_next():
            if time_limit != None and self._time > time_limit:
                self.done = True

    def _finish_send_back(self, to, destination, packet):
        destination.from_network(packet)
        self._scheduled_by_link[to] -= 1

    def send_packet(self, packet, to=None):
        if to not in self._links:
            raise Exception(f'internal error, invalid packet destination {to}')
        self._links[to].enqueue(packet)

    def create_timer(self, timeout, function, description) -> Event:
        event = Event(
            time = self.time() + timeout,
            action = function,
            description = description
        )
        self.add_event(event)
        return event

