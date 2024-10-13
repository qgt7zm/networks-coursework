import argparse
import config
import json
import re
import util
import sys

from util import Message
from simulator import Simulator, Event
from importlib import import_module

def get_class(name, default_module):
    if '.' not in name:
        full_name = default_module + '.' + name
    else:
        full_name = name
    module, class_name = full_name.rsplit(sep='.', maxsplit=-1)
    the_cls = import_module(module).__dict__[class_name]
    return the_cls

def get_buffer_class(args):
    return get_class(args.buffer_class, 'buffer')

def get_receiver_class(args):
    return get_class(args.receiver_class, 'ends')

def get_sender_class(args):
    return get_class(args.sender_class, 'ends')

def run(args):
    _simulator = util._simulator = Simulator(args)
    _simulator.new_link(
        bandwidth=args.bandwidth_forward,
        buffer_size=args.buffer_size,
        buffer_cls=get_buffer_class(args),
        delay=args.delay,
        delay_variance=args.delay_variance,
        drop=args.drop_forward,
        label='forward'
    )
    _simulator.new_link(
        bandwidth=args.bandwidth_backward,
        buffer_size=args.buffer_size,
        buffer_cls=get_buffer_class(args),
        delay=args.delay,
        delay_variance=args.delay_variance,
        drop=args.drop_backward,
        label='backward'
    )
    c1 = _simulator.new_connection(
        label='c1',
        sender=get_sender_class(args)(),
        receiver=get_receiver_class(args)(),
        forward_link_name='forward',
        backward_link_name='backward',
        missing_is_error=False,
    )
    c1.generate_messages(rate=args.c1_rate, total_messages=args.c1_count, mean_size=args.c1_size)
    c2= _simulator.new_connection(
        label='c2',
        sender=get_sender_class(args)(),
        receiver=get_receiver_class(args)(),
        forward_link_name='forward',
        backward_link_name='backward',
        missing_is_error=False,
    )
    c2.generate_messages(rate=args.c2_rate, total_messages=args.c2_count, mean_size=args.c2_size)
    _simulator.run(time_limit = args.time_limit)
    if args.json:
        json_data = {
            'bandwidth_forward': args.bandwidth_forward,
            'delay': args.delay,
            'delay_variance':args.delay_variance,
            'buffer_class': args.buffer_class,
            'c1': c1.json_info(),
            'c2': c2.json_info()
        }
        json.dump(json_data, fp=sys.stdout, indent=2)
    else:
        print(f'forward link: {args.bandwidth_forward:.1f} size units/sec; link delay {args.delay} +/- {args.delay_variance}; {args.buffer_size}-entry {args.buffer_class}')
        c1.print_statistics()
        c2.print_statistics()

def _convert_bool(s: str) -> bool:
    if s == 'true' or s == 'True':
        return True
    elif s == 'false' or s == 'False':
        return False
    else:
        raise ValueError

_convert_bool.__name__ = 'bool'

def _convert_set(s: str) -> [str]:
    if s == '':
        return set([])
    else:
        return set(map(lambda x: x.strip(), s.split(',')))

_convert_set.__name__ = 'comma-separted set of strings'

class SetBothBandwidth(argparse.Action):
    def __call__(self, parser, args, values, option_string):
        setattr(args, 'bandwidth_forward', values)
        setattr(args, 'bandwidth_backward', values)

class SetBothDrop(argparse.Action):
    def __call__(self, parser, args, values, option_string):
        setattr(args, 'drop_forward', values)
        setattr(args, 'drop_backward', values)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--json', default=False, action='store_true',
        help='JSON format output (for grading)'
    )
    input_group = parser.add_argument_group('simulated input/duration settings')
    input_group.add_argument('--time-limit', metavar='UNITS', type=float,
        help='end simulation after UNITS time units (default: 5000)',
        default=5000
    )
    input_group.add_argument('--c1-rate', type=float, help='average input rate (messages/time unit) of connection c1', default=5)
    input_group.add_argument('--c1-size', type=float, help='average message size of connection c1 (default: 100; must be at least 40)', default=100)
    input_group.add_argument('--c1-count', type=int, help='number of messages to generate for connection c1 (default: infinite)', default=None)
    input_group.add_argument('--c2-rate', type=float, help='average input rate (messages/time unit) of connection c2', default=5)
    input_group.add_argument('--c2-size', type=float, help='average message size of connection c2 (defualt: 100; must be at least 40)', default=100)
    input_group.add_argument('--c2-count', type=int, help='number of messages to generate for connection c2 (default: infinite)', default=None)

    sim_group = parser.add_argument_group('simulated link+buffers settings')
    sim_group.add_argument('--drop', metavar='DROP-RATE',
        help='simulated random drop rate in both directions (in addition to drops from buffer limit)',
        type=float, action=SetBothDrop)
    sim_group.add_argument('--drop-forward', metavar='DROP-RATE',
        help='simulated random drop rate sender to receiver (default: 0.0)', default=0.0, type=float)
    sim_group.add_argument('--drop-backward', metavar='DROP-RATE',
        help='simulated random drop rate receiver to sender (default: 0.0)', default=0.0, type=float)
    sim_group.add_argument('--delay', help='minimum simulated link delay (defualt: 1 time unit)', default=1.0, type=float,
        metavar='TIME')
    sim_group.add_argument('--delay-variance', help='average extra random delay; total transmission delay will be the delay setting + an exponentially distributed extra delay (default: 0 extra delay)', default=0.0, type=float,
        metavar='TIME')
    sim_group.add_argument('--bandwidth', help='set simulated link bandwidth in both directions',
        type=float, default=None, action=SetBothBandwidth)
    sim_group.add_argument('--bandwidth-forward', help='simulated link bandwidth to receiver in size per time unit (default: 1000)',
        default=1000.0, type=float)
    sim_group.add_argument('--bandwidth-backward', help='simulated link bandwidth to sender in size per time unit (default: infinite)',
        default=float('inf'), type=float)
    sim_group.add_argument('--buffer-size', help='simulated link buffer size in packets (default: 60)',
        default=60, type=int)
    sim_group.add_argument('--buffer-class', help='link buffer implementation (default: DropTailBuffer))',
        default='buffer.DropTailBuffer', type=str)
    
    config_group = parser.add_argument_group('config.py settings')
    config_items = []
    for item in dir(config):
        if re.match(r'[A-Z]+', item):
            the_type = type(config.__dict__[item])
            normalized_option= item.replace('_', '-').lower()
            if the_type == bool:
                the_type = _convert_bool
            elif the_type == set:
                the_type = _convert_set
            config_group.add_argument(f'--{normalized_option}', f'--{item}',
                action='store',
                dest=item,
                type=the_type,
                default=config.__dict__[item],
                help=f'set config.{item}',
            )
            config_items.append(item)


    ends_group = parser.add_argument_group('implementation of connection ends')
    ends_group.add_argument('--sender-class', default='trivial_ends.TrivialSender',
        help='class to implement sending end (default: trivial_ends.TrivialSender)')
    ends_group.add_argument('--receiver-class', default='trivial_ends.TrivialReceiver',
        help='class to implement receiving end (default: trivial_ends.TrivialReceiver)')

    args = parser.parse_args()
    for item in config_items:
        config.__dict__[item] = args.__dict__[item]
    if args.c1_size < 40 or args.c2_size < 40:
        print("--c1-size and --c2-size must both be greater than 40")
        sys.exit(1)
    run(args)
