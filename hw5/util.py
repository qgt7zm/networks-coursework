import sys

def print_next_hop_table(table, file):
    if table != None:
        file.write("  to:" + (" ".join(map(lambda i: f"{i:6d}", range(len(table))))) + "\n")
        file.write("from:\n")
        file.write("-----" + ("------ " * len(table)) + "\n")
        for i in range(len(table)):
            file.write(f"{i:3d} |")
            for j in range(len(table)):
                if table[i][j] == None or table[i][j] == -1:
                    file.write(f"(none) ")
                else:
                    file.write(f"{table[i][j]:6d} ")
            file.write("\n")
    else:
        file.write("error occurred during simulation, not available")

def print_next_hop_table_delta(actual_table, expected_table, file):
    if actual_table == None:
        file.write("error occurred during simulation, next hops not available")
    for i in range(len(expected_table)):
        for j in range(len(expected_table)):
            if actual_table[i][j] != expected_table[i][j]:
                file.write(f'next hop from {i} to {j} was {actual_table[i][j]}, expected {expected_table[i][j]}\n')
