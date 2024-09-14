## all the options here can be overridden on the command-line

"""one of 'no-ack', 'one-zero', 'sliding', 'variable-sliding'"""
MODE = 'no-ack'

"""initial window size for 'sliding' and 'variable-sliding' mode"""
INITIAL_WINDOW = 5

"""maximum sequence number for packets for 'sliding' and 'variable-sliding' mode; sequence numbers should be in [0, MAXIMUM_SEQUENCE]"""
MAXIMUM_SEQUENCE = 1000000

"""maximum window size for `variable-sliding` mode."""
MAXIMUM_WINDOW = 100

"""default timeout to use for resending packets."""
INITIAL_TIMEOUT = 100

"""types of events to output trace info for.

'all' matches all event, otherwise, name listed much last type passed as first arg to trace() function."""
TRACE = set(['debug'])

