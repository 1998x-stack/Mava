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

"""MADDPG system implementation."""
from types import SimpleNamespace

import reverb

from mava.components import building, execution
from mava.components.tf import building as tf_building
from mava.components.tf import execution as tf_executing
from mava.systems.system import System
from mava.systems.tf.maddpg.builder import MADDPGConfig
from mava.utils import enums


class MADDPG(System):
    def configure(self, config):

        ##############################
        # Data and variable management
        ##############################

        setup = building.SystemSetup(
            network_sampling_setup=enums.NetworkSampler.fixed_agent_networks,
            trainer_networks=enums.Trainer.single_trainer,
            termination_condition=None,
        )

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

        dataset = building.DatasetIterator(
            batch_size=config.batch_size,
            prefetch_size=config.prefetch_size,
        )

        adder = building.ParallelNStepTransitionAdder(
            net_to_ints=config.net_to_ints,
            table_network_config=config.table_network_config,
            n_step=config.n_step,
            discount=config.discount,
        )

        variable_server = tf_building.TFVariableServer(
            checkpoint=config.checkpoint,
            checkpoint_subpath=config.checkpoint_subpath,
            checkpoint_minute_interval=config.checkpoint_minute_interval,
        )

        executor_client = tf_building.TFExecutorVariableClient(
            executor_variable_update_period=config.executor_variable_update_period
        )

        trainer_client = tf_building.TFTrainerVariableClient()

        ##########
        # Executor
        ##########

        observer = execution.Observer()
        preprocess = execution.Batch()
        policy = execution.DistributionPolicy()
        action_selection = tf_executing.OnlineActionSampling()

        executor_components = [
            observer,
            preprocess,
            policy,
            action_selection,
        ]
        executor = building.Executor(executor_components)

        ###########
        # Evaluator
        ###########

        evaluator = building.Executor(executor_components, evaluation=True)

        #########
        # Trainer
        #########

        trainer_components = []
        trainer = building.Trainer(trainer_components)

        #############
        # Distributor
        #############
        distributor = building.Distributor(
            num_executors=config.num_executors,
            nodes_on_gpu=config.nodes_on_gpu,
            name="maddpg",
        )

        ########
        # System
        ########

        return SimpleNamespace(
            setup=setup,
            table=table,
            dataset=dataset,
            adder=adder,
            variable_server=variable_server,
            executor_client=executor_client,
            trainer_client=trainer_client,
            executor=executor,
            evaluator=evaluator,
            trainer=trainer,
            distributor=distributor,
        )


## Example of create/launching system
config = MADDPGConfig(...)
system = MADDPG(config)

# Launch system
system.launch()
