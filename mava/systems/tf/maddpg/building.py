# python3
# Copyright 2021 InstaDeep Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""MADDPG system builder implementation."""

import dataclasses
from typing import Any, Dict, List, Optional, Union
from mava import components

import reverb
import sonnet as snt
from acme.utils import counting, loggers

from mava import specs
from mava.systems.building import OnlineSystemBuilder
from mava.components import building
from mava.components.tf import building as tf_building


@dataclasses.dataclass
class MADDPGConfig:
    """Configuration options for the MADDPG system.
    Args:
        environment_spec: description of the action and observation spaces etc. for
            each agent in the system.
        policy_optimizer: optimizer(s) for updating policy networks.
        critic_optimizer: optimizer for updating critic networks.
        agent_net_keys: (dict, optional): specifies what network each agent uses.
            Defaults to {}.
        checkpoint_minute_interval (int): The number of minutes to wait between
            checkpoints.
        discount: discount to use for TD updates.
        batch_size: batch size for updates.
        prefetch_size: size to prefetch from replay.
        target_averaging: whether to use polyak averaging for target network updates.
        target_update_period: number of steps before target networks are updated.
        target_update_rate: update rate when using averaging.
        executor_variable_update_period: the rate at which executors sync their
            paramters with the trainer.
        min_replay_size: minimum replay size before updating.
        max_replay_size: maximum replay size.
        samples_per_insert: number of samples to take from replay for every insert
            that is made.
        n_step: number of steps to include prior to boostrapping.
        sequence_length: recurrent sequence rollout length.
        period: consecutive starting points for overlapping rollouts across a sequence.
        max_gradient_norm: value to specify the maximum clipping value for the gradient
            norm during optimization.
        sigma: Gaussian sigma parameter.

        checkpoint: boolean to indicate whether to checkpoint models.
        checkpoint_subpath: subdirectory specifying where to store checkpoints.
        replay_table_name: string indicating what name to give the replay table."""

    environment_spec: specs.MAEnvironmentSpec
    policy_optimizer: Union[snt.Optimizer, Dict[str, snt.Optimizer]]
    critic_optimizer: snt.Optimizer
    num_executors: int
    agent_net_keys: Dict[str, str]
    trainer_networks: Dict[str, List]
    table_network_config: Dict[str, List]
    executor_samples: List
    net_to_ints: Dict[str, int]
    unique_net_keys: List[str]
    checkpoint_minute_interval: int
    discount: float = 0.99
    batch_size: int = 256
    prefetch_size: int = 4
    target_averaging: bool = False
    target_update_period: int = 100
    target_update_rate: Optional[float] = None
    executor_variable_update_period: int = 1000
    min_replay_size: int = 1000
    max_replay_size: int = 1000000
    samples_per_insert: Optional[float] = 32.0
    n_step: int = 5
    sequence_length: int = 20
    period: int = 20
    bootstrap_n: int = 10
    max_gradient_norm: Optional[float] = None
    sigma: float = 0.3
    logger: loggers.Logger = None
    counter: counting.Counter = None
    checkpoint: bool = True
    checkpoint_subpath: str = "~/mava/"
    replay_table_name: str = "trainer"  # reverb_adders.DEFAULT_PRIORITY_TABLE


# construct default system components
######################################
config = MADDPGConfig

# Replay table
table = building.OffPolicyReplayTables(
    name=config.replay_table_name,
    sampler=reverb.selectors.Uniform(),
    remover=reverb.selectors.Fifo(),
    max_size=config.max_replay_size,
    rate_limiter=building.OffPolicyRateLimiter(
        samples_per_insert=config.samples_per_insert,
        min_replay_size=config.min_replay_size,
    ),
    signature=building.ParallelSequenceAdderSignature(),
)

# Dataset
dataset = building.DatasetIterator(
    batch_size=config.batch_size,
    prefetch_size=config.prefetch_size,
)

# Adder
adder = building.ParallelNStepTransitionAdder(
    net_to_ints=config.net_to_ints,
    table_network_config=config.table_network_config,
    n_step=config.n_step,
    discount=config.discount,
)

# Variable server and clients
variable_server = tf_building.VariableServer(
    checkpoint=config.checkpoint,
    checkpoint_subpath=config.checkpoint_subpath,
    checkpoint_minute_interval=config.checkpoint_minute_interval,
)

# Executor client
executor_client = tf_building.ExecutorVariableClient(
    executor_variable_update_period=config.executor_variable_update_period
)

# Trainer client
trainer_client = tf_building.TrainerVariableClient()

# Executor
executor = building.Executor(executor_fn=executor_fn)

# Trainer
trainer = building.Trainer(trainer_fn=trainer_fn)

# System
system_components = [
    table,
    dataset,
    adder,
    variable_server,
    executor_client,
    trainer_client,
    executor,
    trainer,
]

system_builder = OnlineSystemBuilder(components=system_components)


######################################