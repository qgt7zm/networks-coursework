'''
Sample file for manually running the simulator.
'''

import network_simulator

# Network 0
#
#    
# E0 
# | \    
# |  \   
# |7  \2 
# |    \ 
# |     \
# E2 --- E1
#     1
#
network0 = [
	[(1, 2), (2, 7)],         # E0
	[(0, 2), (2, 1)],         # E1
	[(0, 7), (1, 1 )],        # E2
]

simulator = network_simulator.NetworkSimulator(network0, 499, 3)
simulator.run()
simulator.display_forwarding_table(0)
simulator.display_forwarding_table(1)
simulator.display_forwarding_table(2)
print(simulator.route_packet(0, 2))
print("Running ....") if input("Run next Simulation Y/N ") == "Y" else exit 

#######################################################################
# EXPECTED RESULT
#######################################################################
# 
# E0 | Cost | Next Hop
# ---+------+---------
# 0  |    0 |        0
# 1  |    2 |        1
# 2  |    3 |        1
# E1 | Cost | Next Hop
# ---+------+---------
# 0  |    2 |        0
# 1  |    0 |        1
# 2  |    1 |        2
# E2 | Cost | Next Hop
# ---+------+---------
# 0  |    3 |        1
# 1  |    1 |        1
# 2  |    0 |        2



# Network 1
#
#    1
# E0 --- E1
# | \    |
# |  \   |
# |7  \3 | 1
# |    \ |
# |     \|
# E3 --- E2
#     2
#
