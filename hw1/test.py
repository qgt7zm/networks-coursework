import argparse
import copy
import importlib
import io
import json
import random
import re
import struct
import sys

from difflib import SequenceMatcher
from math import ceil

random_seed = 0

class Channel:
    def __init__(self):
        self.got_bits = bytearray()

    def send_bits(self, the_bits):
        for the_bit in the_bits:
            if the_bit != 0 and the_bit != 1:
                raise ValueError('got non-bit {}'.format(the_bit))
            self.got_bits += bytes([the_bit])

def _range(i, j):
    if i + 1 == j:
        return f'message #{i}'
    else:
        return f'messages #{i} through #{j-1} (inclusive)'

def _format_message(m):
    if len(m) == 0:
        return '<empty>'
    else:
        return ''.join(list(map(lambda x: '{:02x} '.format(x), m)))

def generate_bits(sender_cls, sent_messages):
    channel = Channel()
    sender = sender_cls(channel)
    message_bytes = 0
    message_count = 0
    message_end_locs = []
    for message in sent_messages:
        messgae = bytes(message)
        message_bytes += len(message)
        message_count += 1
        sender.send_message(message)
        message_end_locs.append(len(channel.got_bits))
    return {
        'bits': channel.got_bits,
        'message_end_locs': message_end_locs
    }

def receive_and_compare(receiver_cls, distorted_bits, sent_messages):
    received_messages = []
    receiver = receiver_cls(lambda x: received_messages.append(bytes(x)))
    for bit in distorted_bits:
        receiver.handle_bit_from_network(bit)

    # normalize messages to ensure difflib doesn't complain about them being unhashable
    sent_messages = list(map(bytes, sent_messages))
    received_messages = list(map(bytes, received_messages))
    matches = SequenceMatcher(a=sent_messages, b=received_messages, autojunk=False)
    compare_text = []
    extra_messages = 0
    corrupted_messages = 0
    missing_messages = 0
    missing_in_results = 0
    maximum_compare_text = 10
    for tag, i1, i2, j1, j2 in matches.get_opcodes():
        if i2 < 0:
            i2 = len(sent_messages) + i2
        if j2 < 0:
            j2 = len(received_messages) + j2
        if tag == 'equal':
            pass
        elif tag == 'delete':
            if len(compare_text) < maximum_compare_text:
                compare_text.append(f'missing input {_range(i1, i2)}')
            else:
                missing_in_results += 1
            missing_messages += (i2 - i1)
        elif tag == 'insert':
            if len(compare_text) < maximum_compare_text:
                compare_text.append(f'extra output {_range(j1, j2)}')
            else:
                missing_in_results += 1
            extra_messages += (j2 -j1)
        elif tag == 'replace':
            input_count = (i2 - i1)
            output_count = (j2 - j1)
            corrupted_messages += min(input_count, output_count)
            if input_count > output_count:
                missing_messages += input_count - output_count
            elif output_count > input_count:
                extra_messages += output_count - input_count
            if len(compare_text) < maximum_compare_text:
                compare_text.append(f'input {_range(i1, i2)} corrupted into output {_range(j1, j2)}')
                for offset in range(min(3, input_count)):
                    compare_text.append(
                                   f'  input message #{i1 + offset} (hexadecimal bytes):\n'
                                   f'    {_format_message(sent_messages[i1+offset])}\n'
                    )
                if input_count > 3:
                    compare_text.append(f'  + {input_count - 3} more')
                for offset in range(min(3, output_count)):
                    compare_text.append(
                                   f'  output message #{j1 + offset} (hexadecimal bytes):\n'
                                   f'    {_format_message(received_messages[j1+offset])}\n'
                    )
                if output_count > 3:
                    compare_text.append(f'  + {output_count - 3} more')
            else:
                missing_in_results += 1
        else:
            raise Exception(f'internal error --- unknown difflib tag {tag}')
    if missing_in_results > 0:
        compare_text.append(f'+ {missing_in_results} more messages, not shown')

    return {
        'extra_messages': extra_messages,
        'corrupted_messages': corrupted_messages,
        'missing_messages': missing_messages,
        'compare_text': compare_text,
    }

def run_one(sender_cls, receiver_cls, distort_function, sent_messages, only_matching=None):
    """Run a test case:

    *  `sender_cls`: class implementing sender; should have __init__ method taking a channel argument.
       We will call its send_message() with a message (in bytes) to send, it should call the channel's
       send_bytes() method.
    *  `receiver_cls`: class implementing receiver; should have __init__ method taking a got_message_function
       argument. We will call the receiver's handle_byte_from_network function, it should call
       got_message_function with a bytes object.
    *  `distort_function_generator`: function to generate array of (label, distort functions)
    *  `sent_messages`: messages to send through Sender's send_message method
    *  `only_matching`: only run subtests whose label matches this regular expression
    """
    send_result = generate_bits(sender_cls, sent_messages)
    distorted_bit_sets = distort_function(send_result)
    results = {
        'message_count': len(sent_messages),
        'message_bytes': sum(map(len, sent_messages)),
        'original_bits': send_result['bits'],
        'original_bit_count': len(send_result['bits']),
        'original_message_end_locs': send_result['message_end_locs'],
        'subtests': []
    }
    for label, distorted in distorted_bit_sets:
        if label != None and only_matching and not re.match(only_matching, label):
            continue
        results['subtests'].append((
            label, receive_and_compare(receiver_cls, distorted, sent_messages)
        ))
    return results

def identity(send_result):
    """Function for 'corrupting' messages that does nothing."""
    return [
        (None, send_result['bits'])
    ]

def get_rng():
    global random_seed
    rng = random.Random(random_seed)
    return rng

def random_messages(length, count):
    rng = get_rng()
    return [rng.randbytes(length) for i in range(count)]

def do_corrupt_random(flip_rate, add_rate, delete_rate, flip_count, add_count, delete_count,
                      corrupt_limit_messages, trials, send_result):
    old_bits = send_result['bits']
    message_ends = send_result['message_end_locs']
    corrupted = []
    for i in range(trials):
        assert len(old_bits) > 0, "sender produced no bytes?"
        new_bits = bytearray(old_bits)
        rng = get_rng()
        if corrupt_limit_messages == None:
            corrupt_limit = len(old_bits)
        else:
            corrupt_limit = message_ends[corrupt_limit_messages - 1]
        if len(old_bits) > 0 and (delete_rate > 0 or delete_count > 0):
            delete_count += ceil(corrupt_limit * delete_rate)
            delete_points = sorted(rng.sample(range(corrupt_limit), delete_count))
            new_bits = bytearray(len(old_bits) - len(delete_points))
            out_loc = 0
            in_loc = 0
            for i in delete_points:
                count = i - in_loc
                new_bits[out_loc:out_loc + count- 1] = old_bits[in_loc:in_loc + count - 1]
                in_loc += count
                in_loc += 1
                out_loc += count
            new_bits[out_loc:] = old_bits[in_loc:]
            old_bits = new_bits
            corrupt_limit = min(corrupt_limit, len(old_bits))
        if len(old_bits) > 0 and (flip_rate > 0 or flip_count > 0):
            flip_count += ceil(corrupt_limit * flip_rate)
            new_bits = bytearray(old_bits)
            flip_points = sorted(rng.sample(range(corrupt_limit), flip_count))
            for i in flip_points:
                new_bits[i] ^= 1
            old_bits = new_bits
        if len(old_bits) > 0 and (add_rate > 0 or add_count > 0):
            add_count += ceil(corrupt_limit * add_rate)
            add_points = sorted(rng.sample(range(corrupt_limit), add_count))
            new_bits = bytearray(len(old_bits) + len(add_points))
            out_loc = 0
            in_loc = 0
            for i in add_points:
                count = i - in_loc
                new_bits[out_loc:out_loc + count] = old_bits[in_loc:in_loc + count]
                in_loc += count
                out_loc += count
                new_bits[out_loc] = rng.randrange(0, 2)
                out_loc += 1
            new_bits[out_loc:] = old_bits[in_loc:]
            old_bits = new_bits
        corrupted.append((f'attempt #{i}', new_bits))
    return corrupted

def make_corrupt_random(flip_rate=0, add_rate=0, delete_rate=0, flip_count=0, add_count=0, delete_count=0,
                        corrupt_limit_messages=None, trails=1):
    """Generate a function to corrupt a message. Parameters:

    *  flip_rate, flip_count: portion/number of bits to flip a bit (at random)
    *  add_rate, add_count: portion/number of bits to add an additional bit to (at random)
    *  delete_rate, delete_count: portion/number of bytes to delete (at random)
    """
    result = lambda send_result: do_corrupt_random(
          send_result=send_result, flip_rate=flip_rate, flip_count=flip_count,
          add_rate=add_rate, delete_rate=delete_rate,
          add_count=add_count, delete_count=delete_count,
          corrupt_limit_messages=corrupt_limit_messages,
          trials=trails
    )
    result.__name__ = 'corrupt ({trails} trials; change bit {flip_rate * 100}% + {flip_count}, add bit {add_rate * 100}% + {add_count}, delete bit {delete_rate * 100}% + {delete_count})' + ('--- but only first {corrupt_limit_portion * 100}% of data')
    return result


def do_corrupt_each(send_result, message_limit, maximum_indices=512):
    """
    Systematically corrupt each bit up to message # message_limit provided
    this is less than maximum_indices bits. If it would be more than maximum_indices
    bits, that many bits are selected rnadomly.
    """
    results = []
    raw_bits = send_result['bits']
    limit_bit_index = send_result['message_end_locs'][message_limit - 1]
    if limit_bit_index > maximum_indices:
        indices = get_rng().sample(range(limit_bit_index), maximum_indices)
    else:
        indices = range(limit_bit_index)
    for i in indices:
        results.append((
            f'flip bit #{i}',
            bytes(raw_bits[0:i] + bytes([raw_bits[i]^1]) + raw_bits[i+1:])
        ))
        results.append((
            f'add zero after #{i}',
            bytes(raw_bits[0:i+1] + bytes([0]) + raw_bits[i+1:])
        ))
        results.append((
            f'add one after #{i}',
            bytes(raw_bits[0:i+1] + bytes([1]) + raw_bits[i+1:])
        ))
        results.append((
            f'delete bit #{i}',
            bytes(raw_bits[0:i] + raw_bits[i+1:])
        ))
    return results

def make_corrupt_each(message_limit):
    return lambda send_result: do_corrupt_each(send_result, message_limit)

def get_results_for(
        label,
        sender_cls,
        receiver_cls,
        distort_function,
        sent_messages,
        maximum_missing=None,
        maximum_corrupted=0,
        maximum_size=None,
        verbose=False,
        only_subtests_matching=None,
    ):
    all_results = run_one(sender_cls, receiver_cls, distort_function, sent_messages, only_matching=only_subtests_matching)
    total_errors = 0
    for k, results in all_results['subtests']:
        cur_messages = [f"{results['extra_messages']} extra; {results['corrupted_messages']} corrupted; {results['missing_messages']} missing; {all_results['message_bytes']} bytes in {all_results['message_count']} messages sent with {all_results['original_bit_count'] / 8} bytes"]
        failed_p = False
        errors = 0
        if results['extra_messages'] > 0:
            cur_messages.append(f"  ERROR --- extra messages")
            errors += 1
        if maximum_missing != None and results['missing_messages'] > maximum_missing:
            cur_messages.append(f"  ERROR --- too many missing messages")
            errors += 1
        if maximum_corrupted != None and results['corrupted_messages'] > maximum_corrupted:
            if maximum_corrupted == 0:
                cur_messages.append(f"  ERROR --- corrupted messages (none expected)")
            else:
                cur_messages.append(f"  ERROR --- more corrupted messages than expected (threshold {maximum_corrupted})")
            errors += 1
        if maximum_size != None and all_results['original_bit_count'] > maximum_size * 8:
            cur_messages.append(f"ERROR --- used too many bytes to send messages ({all_results['original_bit_count']} versus threshold {maximum_size * 8})")
        if verbose:
            for item in results['compare_text']:
                cur_messages.append(f"  {item}")
        results['errors'] = errors
        total_errors += errors
        results['messages'] = cur_messages
    all_results['total_errors'] = total_errors
    return all_results

def print_result_list(args, label, result_list, file=sys.stdout):
    subtests = result_list['subtests']
    if len(subtests) > 1:
        sub_total = len(subtests)
        sub_with_error = 0
        for k, result in subtests:
            if result['errors'] > 0:
                sub_with_error += 1
        print(f'{label}: {sub_total} subtests, {sub_with_error} with errors', file=file)
        for k, result in subtests:
            if result['errors']:
                found_error = True
            if args.verbose or result['errors'] > 0:
                print(f"  {k}: {result['messages'][0]}", file=file)
                for line in result['messages'][1:]:
                    print(f"    {line}", file=sys.stdout)
            if not args.keep_going and result['errors']:
                return
    elif len(subtests) == 0:
        print(f"{label}: all subtests filtered", file=file)
    else:
        result = subtests[0][1]
        print(f"{label}: {result['messages'][0]}", file=file)
        for line in result['messages'][1:]:
            print(f"  {line}", file=file)

def _bits_to_bytes(raw_bits):
    current = 0
    result = bytearray()
    for i, x in enumerate(raw_bits):
        current *= 2
        current += x
        if i % 8 == 0:
            result += bytes([current])
            current = 0
    if len(raw_bits) % 8 != 0:
        result += bytes([current])
    return bytes(result)

def _do_quote_previous_messages(results, previous_test, locations, before, after):
    raw_bits = results[previous_test]['original_bits']
    messages = []
    if before:
        messages += before
    for location in locations:
        messages.append(_bits_to_bytes(raw_bits[location[0]:location[1]]))
    if after:
        messages += after
    return messages

def make_messages_using_sent_bytes(previous_test, locations, before=None, after=None):
    return lambda results: _do_quote_previous_messages(results, previous_test=previous_test, locations=locations, before=before, after=after)


TESTS = [
    ('empty-clean', {
        'distort_function': identity,
        'sent_messages': [b'', b'', b''],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ('tiny-clean1', {
        'distort_function': identity,
        'sent_messages': [b'A', b'B', b'D'],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ('tiny-clean2', {
        'distort_function': identity,
        'sent_messages': [b'ABC', b'C', b'DE'],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ('tiny-clean3', {
        'distort_function': identity,
        'sent_messages': [b'\x00', b'\xFE', b'\x01', b'\x80', b'\xFF'],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ('tiny-clean4', {
        'distort_function': identity,
        'sent_messages': [b'\x00\x00\x00\x00', b'\xFF\xFF\xFE\xFF\xFF'],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ('send-empty-message-bits-in-message', {
        'distort_function': identity,
        'sent_messages_generator': make_messages_using_sent_bytes(
            previous_test='empty-clean',
            locations=[(0, 200), (1, 10 * 8), (0, 5 * 8), (10 * 8, 20 * 8), (0 * 8, 10 * 8), (8, -1)],
            before=[b'before weird messages'],
            after=[b'after weird messages']
        ),
        'maximum_missing': 0,
        'maximum_corrupted': 0,
    }),
    ('send-tiny-clean2-message-bits-in-message', {
        'distort_function': identity,
        'sent_messages_generator': make_messages_using_sent_bytes(
            previous_test='tiny-clean2',
            locations=[(0, 200), (1, 10 * 8), (0, 5 * 8), (10 * 8, 20 * 8), (0 * 8, 10 * 8), (8, -1)],
            before=[b'before weird messages'],
            after=[b'after weird messages']
        ),
        'maximum_missing': 0,
        'maximum_corrupted': 0,
    }),
    ('corrupt-first-recover-tiny1', {
        'distort_function': make_corrupt_each(message_limit=1),
        'sent_messages': [b'x', b'y', b'Z' * 1000, b'Q' * 1000,
                          b'A', b'B', b'C', b'D', b'E', b'F', b'G'],
        'maximum_missing': 4,
        'maximum_corrupted': 0, # probability of checksum not working should be negligible for such a small message
        'maximum_size': 120 * 9 + 1201 * 2,
    }),
    ('corrupt-first-recover-tiny2', {
        'distort_function': make_corrupt_each(message_limit=1),
        'sent_messages': [b'\xFE', b'\xFE', b'\x00' * 1000, b'\x00' * 1000, 
                          b'A', b'B', b'C', b'D', b'E', b'F', b'G'],
        'maximum_missing': 4,
        'maximum_corrupted': 0, # probability of checksum not working should be negligible for such a small message
        'maximum_size': 120 * 9 + 1201 * 2,
    }),
    ('allbytes-clean', {
        'distort_function': identity,
        'sent_messages': [bytes([x]) for x in range(256)],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 256,
    }),
    ('allbytes-dupd-clean', {
        'distort_function': identity,
        'sent_messages': [bytes([x] * 60) for x in range(256)],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 256,
    }),
    ('three-message-clean', {
        'distort_function': identity,
        'sent_messages': [b'message 1', b'message 2', b'message 3'],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ('many-message-corrupt-recover', {
        'distort_function': make_corrupt_random(flip_rate=0.0001, add_rate=0.0001, delete_rate=0.0001, corrupt_limit_messages=100),
        'sent_messages': list(map(lambda x: f'{struct.pack("H", x)}{b"Q" * (1+(x*137)%7)}'.encode('us-ascii'), range(1000))),
        # first 100 badly corrupted, should recover within a couple kilobytes of messages, which pessimistically might be 300 messages
        'maximum_missing': 100 + 300,
        'maximum_corrupted': 1,
        'maximum_size': 120 * 1000,
    }),
    ('many-message-corrupt-recover2', {
        'distort_function': make_corrupt_random(flip_rate=0.0001, add_rate=0.0001, delete_rate=0.0001, corrupt_limit_messages=100),
        'sent_messages': list(map(lambda x: f'{struct.pack("H", x)}{bytes([x % 255]) * (1+(x*137)%7)}'.encode('us-ascii'), range(10000))),
        'maximum_missing': 100 + 300,
        'maximum_corrupted': 1,
        'maximum_size': 120 * 10000,
    }),
    ('with-empty-message-clean', {
        'distort_function': identity,
        'sent_messages': [b'before', b'', b'after'],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 3,
    }),
    ( 'three-message-binary-clean', {
        'distort_function': identity,
        'sent_messages': [
            b'\x00\x01\x02\x03message 1' + bytes(range(256)),
            b'\x0a\x0d\x00\x0d\x0amessage 2' + bytes(range(128, 256)) + bytes(range(0, 128)),
            b'\x9a\x00message 1' + bytes(range(128, 256)) + bytes(range(1, 128, 5)),
        ],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': (270 * 3) * 1.21,
    }),
    ( 'three-message-long-binary-clean', {
        'distort_function': identity,
        'sent_messages_generator': lambda _: random_messages(length=300, count=5),
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': (300 * 5) * 1.21 + 10,
    }),
    ('three-long-message-clean', {
        'distort_function': identity,
        'sent_messages': [b'message 1 ' + (b'X' * 1000), b'message 2' + (b'Y' * 999), b'message 3' + (b'XY' * 501)],
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': (1020 + 1020 + 520) * 1.21,
    }),
    ('many-message-clean', {
        'distort_function': identity,
        'sent_messages': list(map(lambda x: f'{x}'.encode('us-ascii'), range(1000))),
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 120 * 1000,
    }),
    ('many-message-clean-varlen', {
        'distort_function': identity,
        'sent_messages': list(map(lambda x: f'{x} {"Z" * ((x*137)%131)}'.encode('us-ascii'), range(1000))),
        'maximum_missing': 0,
        'maximum_corrupted': 0,
        'maximum_size': 140 * 1.2 * 1000,
    }),
    ('many-message-corrupt', {
        'distort_function': make_corrupt_random(flip_count=20),
        'sent_messages': list(map(lambda x: f'this is message {x} XXXXX XXXXX XXXXX'.encode('us-ascii'), range(10000))),
        # With this rate of corruption, we'd estimate around 20 messages corrupted.
        # Assume at most 25 extra messages are corrupted due to desync
        'maximum_missing': 20 * 25,
        'maximum_corrupted': 1,
        'maximum_size': 120 * 10000,
    }),
    ('many-message-corrupt2', {
        'distort_function': make_corrupt_random(add_rate=0.00025 / 8, delete_rate=0.00025 / 8),
        'sent_messages': list(map(lambda x: f'message {x}'.encode('us-ascii'), range(1000))),
        'maximum_missing': 120,
        'maximum_corrupted': 1,
        'maximum_size': 120 * 1000,
    }),
    ('many-message-corrupt-varlen', {
        'distort_function': make_corrupt_random(flip_count=20),
        'sent_messages': list(map(lambda x: f'message {x} {"Z" * ((x*137)%131)}'.encode('us-ascii'), range(1000))),
        'maximum_missing': 120,
        'maximum_corrupted': 1,
        'maximum_size': 140 * 1.2 * 1000,
    }),
    ('many-message-corrupt-varlen2', {
        'distort_function': make_corrupt_random(flip_rate=0.00003 / 8, add_rate=0.00003 / 8, delete_rate=0.00003 / 8),
        'sent_messages': list(map(lambda x: f'message {x} {"Z" * ((x*137)%131)}'.encode('us-ascii'), range(10000))),
        'maximum_missing': 1200,
        'maximum_corrupted': 1,
        'maximum_size': 150 * 1.2 * 10000,
    }),
    ('many-message-corrupt-varlen3', {
        'distort_function': make_corrupt_random(add_count=10, delete_count=10),
        'sent_messages': list(map(lambda x: f'{struct.pack("H", x)}{bytes([x % 255]) * (1+(x*137)%7)}'.encode('us-ascii'), range(10000))),
        # guess around 20 messages corrupted, and each corrupted message causing 200 mesages to be missed due to
        # desync at most
        'maximum_missing': 4000,
        'maximum_corrupted': 1,
        'maximum_size': 120 * 10000,
    }),
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-module', default='sendrecv',
        help='python module to test (default: sendrecv, meaning sendrecv.py)')
    parser.add_argument('--sender-class', default='MySender',
        help='sender class to test (default: MySender)')
    parser.add_argument('--receiver-class', default='MyReceiver',
        help='receiver class to test (defualt: MyReceiver)')
    parser.add_argument('--random-seed', default=42, type=int,
        help='random seed to use for random parts of tests')
    parser.add_argument('--keep-going', default=False, action='store_true',
        help='keep going after first failure')
    parser.add_argument('--verbose', action='store_true', default=False,
        help='enable verbose output')
    parser.add_argument('--only-test', default=None, type=str,
        help='only run tests matching a specified regular expression')
    parser.add_argument('--only-subtest', default=None, type=str,
        help='only run subtests matching a specified regular expression')
    parser.add_argument('--json', default=False, action='store_true',
        help='JSON-format output (for grading)')
    args = parser.parse_args()
    global random_seed
    random_seed = args.random_seed
    module = importlib.import_module(args.test_module)
    sender_cls = module.__dict__[args.sender_class]
    receiver_cls = module.__dict__[args.receiver_class]
    
    global TESTS
    failure = False
    results = {}
    for label, test_args in TESTS:
        if args.only_test and not re.match(args.only_test, label):
            continue
        test_args = copy.copy(test_args)
        if test_args.get('sent_messages_generator'):
            test_args['sent_messages'] = test_args['sent_messages_generator'](results)
            del test_args['sent_messages_generator']
        results[label] = get_results_for(label=label,
            sender_cls=sender_cls, receiver_cls=receiver_cls,
            verbose=args.verbose,
            only_subtests_matching=args.only_subtest,
            **test_args)
        if results[label]['total_errors'] > 0:
            failure = True
        if not args.json:
            print_result_list(args, label, results[label], file=sys.stdout)
        else:
            msg_out = io.StringIO()
            print_result_list(args, label, results[label], file=msg_out)
            results[label]['messages'] = msg_out.getvalue()
        if failure and not args.keep_going:
            break
    if args.json:
        for _, test_data in results.items():
            del test_data['original_bits']
            del test_data['original_message_end_locs']
        json.dump(results, indent=4, fp=sys.stdout)
    else:
        if failure and not args.keep_going:
            print("*** a test failed. stopped.")
        elif failure:
            print("*** at least one test failed.")
        else:
            print("*** all tests passed.")

    

if __name__ == '__main__':
    main()
