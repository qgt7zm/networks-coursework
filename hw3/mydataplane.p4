/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
const bit<8> TYPE_ICMP = 0x01;

const bit<32> TO_CONTROLLER_CLONE_SESSION_ID = 1;
const bit<8>  TO_CONTROLLER_CLONE_FIELD_LIST = 1;

#define NUM_PORT_IDS 512
#define CPU_PORT_ID 510


/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;

/*
 * Ethernet header. Note that this needs to exactly mach the layout of ethernet frames,
 * and so cannot be changed.
 */
header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

/*
 * Extra information sent alongside packets when sending to the controller.
 *
 * Based on the perspective of the controller this is named "packet in", because
 * the messages that send the packet to the controller are called PacketIn
 * messages.
 *
 * This information is extracted by the supplied process_packet() function
 * in mycontroller.py
 */
@controller_header("packet_in")
header packet_in_header_t {
    bit<16> inPort;
}

/*
 * Headers to track for each packet.
 *
 * Since this is just a layer-2 switch, we do not parse IPv4 or IPv6 headers.
 *
 * The `packet_in` headers represents the extra information to be sent
 * to the controller. In MyEgress() below, we mark this header as "invalid"
 * when sending to a host, so that it is not emitted by MyDeparse().
 */
struct headers {
    packet_in_header_t packet_in;
    ethernet_t      ethernet;
}

/*
 * Extra metadata for the program to use. You can use this if you want to track information
 * about packets outside the headers.
 *
 * Note that this is different than the `standard_metadata`, which includes metadata used by
 * the internals of the switch, such as where to send packets.
 */
struct metadata {
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition parse_packet_in;
    }

    state parse_packet_in {
        hdr.packet_in.setValid();
        hdr.packet_in.inPort = (bit<16>)standard_metadata.ingress_port;
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {


    action drop() {
        mark_to_drop(standard_metadata);
    }

    /* Set the destination port of the packet.
     * Note that field is called `egress_spec` and not `egress_port`;
     * there is a field called `egress_port`, but you should not write to it
     * (it's there only to be read in MyEgress())
     */
    action forward_to_port(egressSpec_t port) {
        standard_metadata.egress_spec = port;
    }

    /* Set a packet to be broadcast by all output ports.
     * This uses the "multicast" (send to multiple) feature of the switch,
     * which is configured in mycontroller.py. The multicast group number (1)
     * has to match that configuration.
     *
     * This queues the packet for all output ports (except the "CPU port" to
     * the controller). Code in MyEgress prevents packets from being transmitted
     * back on the port they came in on.
     */
    action broadcast() {
        standard_metadata.mcast_grp = 1;
    }

    /* Set a packet to be copied to the controller.
     * This uses a "clone session" that is configured in mycontroller.py.
     *
     * "I2E" indicates "ingress-to-egress", since we are cloning the packet
     * in the ingress processing and want it to be next processed by the egress
     * processing.
     */
    action copy_to_controller() {
        clone_preserving_field_list(
            CloneType.I2E,
            TO_CONTROLLER_CLONE_SESSION_ID,
            0
        );
    }

    /*
     * Table to decide what to do with packets based on their destination ethernet addresses.
     *
     * With the default settings, each packet is broadcast to all output ports except the
     * one it came in on.
     *
     * Without any changes being made to this file, the controller can add entries to this table
     * to make MAC addresses or ranges of MAC addresses forward to a particular port.
     */
    table mac_dst_lpm {
        key = {
            hdr.ethernet.dstAddr : lpm;
        }
        actions = {
            forward_to_port;
            broadcast;
            NoAction;
        }
        size = 1024;
        default_action = broadcast;
    }


    apply {
        // TODO:
            // add code here to run copy_to_controller()
            // ideally, this would be done with a table to avoid copying to controller
            // for uninteresting packets
        mac_dst_lpm.apply();
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    counter(NUM_PORT_IDS, CounterType.packets_and_bytes) egressCounter;
    apply {
        /*
         * egress_port represents the destination of this packet.
         * For packets that are sent multiple times, MyEgress() will run one time for
         * each time the packet is output. Note that if you want to direct where
         * packets go, you should NOT set egress_port (instead set egress_spec,
         * mcast_grp, or use a clone function, as shown in the supplied code above).
         *
         * Packets that are about to be sent to the controller will go to port
         * CPU_PORT_ID (510), which is configured as the "CPU port" in topology.json.
         *
         * Packets that are not being sent to the controller should not have the
         * "packet in" metadata included, so we mark that header invalid. If we
         * fail to do this, it would be added to the data sent over the (emulated)
         * Ethernet connection.
         */
        if (standard_metadata.egress_port != CPU_PORT_ID) {
            hdr.packet_in.setInvalid();
        }

        /*
         * When we broadcast a packet, it is replicated to _all_ ports, which
         * would normally cause somone to receive packets that they are
         * broadcasting back. We prevent this by dropping the packets here.
         */
        if (standard_metadata.ingress_port == standard_metadata.egress_port) {
            mark_to_drop(standard_metadata);
        }

        /* Increment a counter that can be quired by print_counters.py. */
        egressCounter.count((bit<32>) standard_metadata.egress_port);
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
    apply {
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.packet_in);
        packet.emit(hdr.ethernet);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
