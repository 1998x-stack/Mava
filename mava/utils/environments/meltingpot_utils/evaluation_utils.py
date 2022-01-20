from ast import Dict
from collections.abc import Callable
from typing import Any

import sonnet as snt

from mava import core
from mava.environment_loop import ParallelEnvironmentLoop

# Types
MAVASystem = Any
AgentNetworks = Dict[str, snt.Module]


class ScenarioEvaluation:
    def __init__(
        self,
        scenario_system: MAVASystem,
        evaluator_loop_creator: Callable[[MAVASystem], ParallelEnvironmentLoop],
        agent_network_setter: Callable[[core.Executor, AgentNetworks], None],
        trained_networks: AgentNetworks,
    ) -> None:
        """Evaluates a system on a meltingpot scenario

        Args:
            scenario_system (MAVASystem): A system created using a scenario's
                environment spec
            evaluator_loop_creator (Callable[[MAVASystem], ParallelEnvironmentLoop]): A
                callback function that creates the evaluation loop given a system
            agent_network_setter (Callable[[core.Executor, Networks], None]): A callback
                function that samples from trained networks (trained in the substrate)
                to create networks for agents in the scenario
            trained_networks (Networks): Trained networks for agents from the substate
        """
        self._system = scenario_system
        self._evaluator_loop = evaluator_loop_creator(self.system)
        self._trained_networks = trained_networks
        agent_network_setter(self._evaluator_loop._evaluator, trained_networks)

    def run(self) -> None:
        """Runs an episode using the evaluator loop"""
        self._evaluator_loop.run(num_episodes=1)
