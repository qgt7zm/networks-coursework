import copy


class Packet:
    '''
    Class representing a packet being sent between neighboring nodes one-hop
    from each other.
    '''

    def __init__(self, destination, costs):
        '''
        Create a packet containing DV cost information. Source is not required
        when creating a packet as that will automatically be filled in by the
        simulator.

        Arguments:
        - `destination`: The entity index of the recipient node.
        - `costs`:       An array with a length equivalent to the number of
                         entities in the network. Each value in the array should
                         be the cost from the sender to the entity with that
                         index.

        Return Value: None
        '''
        self.destination = destination
        self.costs = copy.deepcopy(costs)

    def get_source(self):
        '''
        Return the source index of the packet.

        Return Value: The entity index of the sender of this packet.
        '''
        return self.source

    def get_costs(self):
        '''
        Return the cost values sent in the packet.

        Return Value: The array of costs transmitted by this packet.
        '''
        return self.costs

    def set_source(self, source):
        '''
        Manually set the source of the packet. This should only be called by the
        simulator.
        '''
        self.source = source

    def get_destination(self):
        '''
        Return the destination of the packet. This likely only needs to be
        called by the simulator.
        '''
        return self.destination
