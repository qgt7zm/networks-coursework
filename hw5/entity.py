'''
Code for an entity in the network. This is where you should implement the
distance-vector algorithm.
'''

from packet import Packet
import math

class Entity:
    '''
    Entity that represents a node in the network.

    Each function should be implemented so that the Entity can be instantiated
    multiple times and successfully run a distance-vector routing algorithm.
    '''

    def __init__(self, entity_index, number_entities):
        '''
        This initialization function will be called at the beginning of the
        simulation to set up all entities.

        The skeleton code version of this method sets some convenient instance
        variables you may find useful:
        - self.index --- this entity's index
        - self.number_of_entities --- the total number of entities
        - self.cost_table --- an array of costs, initially all math.inf (infinity)
        - self.next_hop_table --- an array of next hops, initially all None
        - self.neighbor_cost_map --- a dict for storing direct links from this entity, initially empty

        You are not required to use these instance variables (though I did so
        in my reference implementation).

        Arguments:
        - `entity_index`:    The id of this entity.
        - `number_entities`: Number of total entities in the network.

        Return Value: None.
        '''
        # Save state
        self.index = entity_index
        self.number_of_entities = number_entities

        '''
        Initialize parallel arrays for cost, next_hop.

        This matches what is shown in section 3.4.2 of the textbook, but if you
        want to do some other sort of bookkeeping, that is fine, but you'll need
        to change the supplied code for forward_next_hop() and
        get_all_costs().
        '''
        self.cost_table = [math.inf for i in range(self.number_of_entities)]
        self.next_hop_table = [None for i in range(self.number_of_entities)]

        # Map of entity-to-cost for the neighbors of this entity.
        # In __init__, we set costs all to infinity. 
        # We supply code that sets this in the initialize_costs() method.
        self.neighbor_cost_map = {}

    def initialize_costs(self, neighbor_costs):
        '''
        This function will be called at the beginning of the simulation to
        provide a list of neighbors and the costs on those one-hop links.

        The skeleton code version of this function sets self.neighbor_cost_map,
        but does not return any needed update Packets.

        Arguments:
        - `neighbor_costs`:  Array of (entity_index, cost) tuples for
                             one-hop neighbors of this entity in this network.

        Return Value: This function should return an array of `Packet`s to be
        sent from this entity (if any) to neighboring entities.
        '''
        # print(f"Self: {self.index}")

        # Add neighbor costs
        for k, v in neighbor_costs:
            self.neighbor_cost_map[k] = v
            # print(f"- To = {k}, Cost = {v}")

        # Get all costs in table
        costs = []
        for i in range(self.number_of_entities):
            if i == self.index:
                costs.append(0)  # cost to self is 0
            else:
                costs.append(self.neighbor_cost_map[i])  # cost to neighbor

        # Send packets to direct neighbors
        packets = []
        for k in self.neighbor_cost_map.keys():
            packets.append(Packet(destination=k, costs=costs))
        return packets

    def update(self, pkt):
        '''
        This function is called when a packet arrives for this entity.

        Arguments:
        - `packet`: The incoming packet of type `Packet`.

        Return Value: This function should return an array of `Packet`s to be
        sent from this entity (if any) to neighboring entities.
        '''
        source = pkt.get_source()
        print(f"Self: {self.index}")

        for destination, cost in enumerate(pkt.get_costs()):
            # Calculate path cost
            print(f"- Got: From = {source}, To = {destination}, Cost = {cost}")
            old_path_cost = self.cost_table[destination]
            new_path_cost = self.neighbor_cost_map[source] + cost
            print(f"- Old = {old_path_cost}, New = {new_path_cost}")

            # Update routing table
            if new_path_cost < old_path_cost:
                self.cost_table[destination] = new_path_cost
                self.next_hop_table[destination] = source

        # FIXME part 1: return array of packets to send to neighbors for needed updates
        return []

    def periodic_update(self):
        '''
        Called to generate a set of messages that would be part of a periodic update.

        The skeleton code version of this sends nothing.

        Return Value: This should return an array of `Packet`s to be sent to this entity
        to neighboring entities. Unlike other methods, this should send updates even when
        they do not appear necessary due to recent routing table changes.
        '''
        return []

    def add_neighbor(self, neighbor_index, link_cost):
        '''
        Called to add a _new_ link to a neighbor.

        The skeleton code version of this just updates `self.neighbor_cost_map`,
        but does not update any other tables. I would recommend modifying this
        to update `cost_table` and `next_hop_table` if this new link is
        better than the current route, and then to compute which packets
        to send.

        Arguments:
        - `neighbor_index`:  The zero-based index of the new neighbor.
        - `link_cost`:  The cost of the link to the new neighbor.

        Return Value: This function should return an array of `Packet`s to be
        sent from the entity to neighboring entites (if warranted by
        adding the new link).
        '''
        self.neighbor_cost_map[neighbor_index] = link_cost
        return []

    def delete_neighbor(self, neighbor_index):
        '''
        Called to mark the link to a neighbor as down.

        The skeleton code version of this just updates `self.neighbor_cost_map`,
        but does not update any other tables.

        I would recommend modifying this to scan through `next_hop_table` to
        replace any routes that use this link.

        Arguments:
        - `neighbor_index`:  The zero-based index of the new neighbor.

        Return Value: This function should return an array of `Packet`s to be
        sent from the entity to neighboring entites if there were changes to
        this node's routing table.
        '''
        del self.neighbor_cost_map
        return []


    def forward_next_hop(self, destination):
        '''
        Return the best next hop for a packet with the given destination.

        The skeleton code version of this reads from `self.next_hop_table`.
        If you use that in your other code, you should not need to change it.

        Arguments:
        - `destination`: The final destination of the packet.

        Return Value: The index of the best neighboring entity to use as the
        next hop. If there is no route to the destination, return either -1 or None.
        If the destination is this entity, return this entity's index.
        '''
        if destination == self.index:
            return self.index
        return self.next_hop_table[destination]

    def get_all_costs(self):
        '''
        This function is used by the simulator to retrieve the calculated routes
        and costs from an entity. This allows the simulator's display_forwarding_table()
        function to work, but is otherwise not used (so your submission will pass test.py
        if this does not work).

        The skeleton code version of this reads from `self.cost_table`.
        If you use that in your other code, it should work without changes.

        Return Value: This function should return an array of (next_hop, cost)
        tuples for _every_ entity in the network based on the entity's current
        understanding of those costs. The array should be sorted such that the
        first element of the array is the next hop and cost to entity index 0,
        second element is to entity index 1, etc.
        '''
        array_of_tuples = []
        for index in range(0, self.number_of_entities):
            next_hop = self.forward_next_hop(index)
            array_of_tuples.append((next_hop, self.cost_table[index]))
        return array_of_tuples
