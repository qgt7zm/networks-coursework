#!/usr/bin/env python3

# Adapted from exercises/p4runtime

import argparse
import os
import sys
from time import sleep

# Utility functions provided to interact with the switch.
from myutil import install_table_entry, read_table_entries, \
                   print_counter, \
                   write_table_entry, write_or_overwrite_table_entry, \
                   decode_packet_in_metadata

from scapy.layers.l2 import Ether
import scapy.all

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections

import grpc


def process_packet(p4info_helper, switch, packet):
    """
    Called by main() for each packet sent from the data plane to the controller.
    In the default implementation, just output the information.
    """
    frame = Ether(packet.payload)
    print("-----------------------------")
    print("Packet received by controller:")
    metadata = decode_packet_in_metadata(
        p4info_helper,
        switch,
        packet.metadata
    )
    # print(f"Controller metadata = {metadata}")
    # print("Packet dump")
    # frame.show()
    
    print(f"Src = {frame.src}")
    print(f"Dest = {frame.dst}")
    print(f"Port = {metadata['inPort'][0]}")
    print(f"Version = {frame.version}")
    print("-----------------------------")
    print("")

    # Hardcode a table entry for h1
    """
    write_or_overwrite_table_entry(
        p4info_helper=p4info_helper,
        switch=switch,
        table_name='MyIngress.mac_dst_lpm',
        match_fields={
            # first 48 bits match this MAC address
            'hdr.ethernet.dstAddr': ('08:00:00:00:01:01', 48),
        },
        action_name='MyIngress.forward_to_port',
        action_params={
            'port': 1,
        }
    )
    """
    
    # Attempt to filter out extraneous IPv6 packets
    # Not working
    if frame.version == 4:
        # print("Forwarding IPv4 packet")
        key = frame.src
        action_name = 'MyIngress.forward_to_port'
        action_params = {
            'port': metadata['inPort'][0]
        }
    else:
        # print("Dropping IPv6 packet")
        key = frame.dst
        action_name = 'NoAction'
        action_params = {}

    # Dynamically update the tables

    # Make sure each host only receives packets meant for it
    write_or_overwrite_table_entry(
        p4info_helper=p4info_helper,
        switch=switch,
        table_name='MyIngress.mac_dst_lpm',
        match_fields={
            # first 48 bits match this MAC address
            'hdr.ethernet.dstAddr': (frame.src, 48),
        },
        action_name=action_name,
        action_params=action_params
    )

    # Limit how many packets the controller receives from pings
    write_or_overwrite_table_entry(
        p4info_helper=p4info_helper,
        switch=switch,
        table_name='MyIngress.mac_src_lpm',
        match_fields={
            # first 48 bits match this MAC address
            'hdr.ethernet.srcAddr': (frame.src, 48),
        },
        action_name='NoAction',
        action_params={
        }
    )

def main(p4info_file_path, bmv2_file_path):
    """
    Run the switch controller, where `p4info_file_path` and `bmv2_file_path`
    are files created by `make` from the .p4 file.
    """
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        # Create a switch connection object for s1
        # Also, dump all P4Runtime messages sent to switch to given txt files.
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')

        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()

        # Load the p4 program into the switch
        s1.SetForwardingPipelineConfig(
            p4info=p4info_helper.p4info,
            bmv2_json_file_path=bmv2_file_path
        )

        # Configure ports on the switch to allow the program to send packets to multiple destinations:
            # Add a "multicast group" with ID 1. This means that if during ingress processing of a packet
            # we set standard_metadata.mcast_grp = 1, the packet will be replicated as specified below.
            # In this case, we specify that it should be replicated to go to output ports 1, 2, 3, and 4.
            # mydataplane.p4 uses this to implement packet broadcast.

            # The "instance" field, which we leave at 0, can be queried by the packet processing code
            # if its logic should be different depending on how the packet is produced
        s1.WritePREEntry(
            p4info_helper.buildMulticastGroupEntry(
                multicast_group_id=1, 
                replicas=[
                    {'egress_port': 1, 'instance': 0},
                    {'egress_port': 2, 'instance': 0},
                    {'egress_port': 3, 'instance': 0},
                    {'egress_port': 4, 'instance': 0},
                ]
            )
        )

            # Add a "clone session" with ID 1.
            #
            # This means that when we run clone_preserving_field_list(1, ...), new copies of the
            # packet set to go to the ports specified below.
            # 
            # We specify it should go to port 510, which we assign to be sent to the controller.
            # cs4457_f24.p4 uses this to implement "send to controller" functionality.

        s1.WritePREEntry(
            p4info_helper.buildCloneSessionEntry(
                clone_session_id=1, 
                replicas=[
                    {'egress_port': 510, 'instance': 1},
                ]
            )
        )

        # Read packets sent to the controller by the switch
        # The switch can send back multiple types of messages, so we filter for those
        # that represents packets.
        for item in s1.stream_msg_resp:
            if item.HasField('packet'):
                process_packet(p4info_helper, s1, item.packet)
    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/mydataplane.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/mydataplane.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)
