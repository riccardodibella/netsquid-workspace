import netsquid as ns
from netsquid.nodes import Node
from netsquid.components.models import DelayModel
from netsquid.components import QuantumChannel
from netsquid.nodes import DirectConnection
from netsquid.protocols import NodeProtocol

from netsquid.components import QuantumProcessor
from netsquid.qubits import qubitapi as qapi

from random_clifford_lib import *

class PingPongDelayModel(DelayModel):
    def __init__(self, speed_of_light_fraction=0.5, standard_deviation=0.05):
        super().__init__()
        # (the speed of light is about 300,000 km/s)
        self.properties["speed"] = speed_of_light_fraction * 3e5
        self.properties["std"] = standard_deviation
        self.required_properties = ['length']  # in km

    def generate_delay(self, **kwargs):
        avg_speed = self.properties["speed"]
        std = self.properties["std"]
        # The 'rng' property contains a random number generator
        # We can use that to generate a random speed
        speed = self.properties["rng"].normal(avg_speed, avg_speed * std)
        delay = 1e9 * kwargs['length'] / speed  # in nanoseconds
        return delay


class LocalPingPongProtocol(NodeProtocol):
    def __init__(self, node, m, local_seed, remote_seed):
        super().__init__(node)
        random_clifford_set_seed(local_seed)
        self.local_clifford_list = [get_random_clifford() for i in range(m)]
        random_clifford_set_seed(remote_seed)
        self.remote_clifford_list = [get_random_clifford() for i in range(m)]

        # Create a noiseless quantum processor with 1 qubit
        # self.qprocessor = QuantumProcessor("loc_processor", num_positions=1, properties={"ports": {"qin": self.node.ports["qubitIO"], "qout": self.node.ports["qubitIO"]}})
        self.qprocessor = QuantumProcessor("loc_processor", num_positions=1)
        self.node.add_subcomponent(self.qprocessor)
        self.node.ports["qubitIO"].forward_input(self.qprocessor.ports["qin"])
        self.qprocessor.ports["qout"].forward_output(self.node.ports["qubitIO"])

    def run(self):

        # Put qubit at position 0 (automatically initialized to |0>)
        self.qprocessor.put(ns.qubits.create_qubits(1))
        self.qprocessor.pop([0])

        for i in range(len(self.local_clifford_list)):
            print("waiting local...")
            yield self.await_port_input(self.qprocessor.ports["qin"])
            print("local RX")
            self.qprocessor.operate(get_operator_from_clifford(self.local_clifford_list[i]), positions=[0])
            self.qprocessor.pop([0])
        
        print("---- local end ----")

class RemotePingPongProtocol(NodeProtocol):
    def __init__(self, node, m, seed):
        super().__init__(node)
        random_clifford_set_seed(seed)
        self.clifford_list = [get_random_clifford() for i in range(m)]

        # Create a noiseless quantum processor with 1 qubit
        # self.qprocessor = QuantumProcessor("rem_processor", num_positions=1, properties={"ports": {"qin": self.node.ports["qubitIO"], "qout": self.node.ports["qubitIO"]}})

        self.qprocessor = QuantumProcessor("rem_processor", num_positions=1)
        self.node.add_subcomponent(self.qprocessor)
        self.node.ports["qubitIO"].forward_input(self.qprocessor.ports["qin"])
        self.qprocessor.ports["qout"].forward_output(self.node.ports["qubitIO"])

    def run(self):

        for i in range(len(self.clifford_list)):
            print("waiting remote...")
            yield self.await_port_input(self.qprocessor.ports["qin"])
            print("remote RX")
            self.qprocessor.operate(get_operator_from_clifford(self.clifford_list[i]), positions=[0])
            self.qprocessor.pop([0])
        
        print("---- remote end ----")



        

    


m = 10
local_seed = 0
remote_seed = 2



loc_node = Node(name="Ping")
rem_node = Node(name="Pong")

distance = 2.74 / 1000  # default unit of length in channels is km
delay_model = PingPongDelayModel()
channel_1 = QuantumChannel("ch1", length=distance, models={"delay_model": delay_model})
channel_2 = QuantumChannel("ch2",length=distance, models={"delay_model": delay_model})


connection = DirectConnection("conn", channel_AtoB=channel_1, channel_BtoA=channel_2)
loc_node.connect_to(remote_node=rem_node, connection=connection, local_port_name="qubitIO", remote_port_name="qubitIO")



loc_pr = LocalPingPongProtocol(loc_node, m, local_seed=local_seed, remote_seed=remote_seed)
rem_pr = RemotePingPongProtocol(rem_node, m, remote_seed)

rem_pr.start()
loc_pr.start()
run_stats = ns.sim_run(duration=10e9)

print(run_stats)
