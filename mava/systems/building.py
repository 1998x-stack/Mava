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

"""MADDPG scaled system builder implementation."""

import abc
from typing import Any, Dict, Iterator, List, Optional

import reverb
import sonnet as snt
import tensorflow as tf
from dm_env import specs as dm_specs

from mava import adders, core, specs, types
from mava.systems.tf.variable_sources import VariableSource as MavaVariableSource
from mava.callbacks import Callback
from mava.systems.callback_hook import SystemCallbackHookMixin

BoundedArray = dm_specs.BoundedArray
DiscreteArray = dm_specs.DiscreteArray


class SystemBuilder(abc.ABC):
    """Builder for systems which constructs individual components of the
    system."""

    @abc.abstractmethod
    def make_replay_tables(
        self,
        environment_spec: specs.MAEnvironmentSpec,
    ) -> List[reverb.Table]:
        """ "Create tables to insert data into.
        Args:
            environment_spec (specs.MAEnvironmentSpec): description of the action and
                observation spaces etc. for each agent in the system.
        Returns:
            List[reverb.Table]: a list of data tables for inserting data.
        """

    @abc.abstractmethod
    def make_dataset_iterator(
        self,
        replay_client: reverb.Client,
        table_name: str,
    ) -> Iterator[reverb.ReplaySample]:
        """Create a dataset iterator to use for training/updating the system.
        Args:
            replay_client (reverb.Client): Reverb Client which points to the
                replay server.
        Returns:
            [type]: dataset iterator.
        Yields:
            Iterator[reverb.ReplaySample]: data samples from the dataset.
        """

    @abc.abstractmethod
    def make_adder(
        self,
        replay_client: reverb.Client,
    ) -> Optional[adders.ParallelAdder]:
        """Create an adder which records data generated by the executor/environment.
        Args:
            replay_client (reverb.Client): Reverb Client which points to the
                replay server.
        Returns:
            Optional[adders.ParallelAdder]: adder which sends data to a replay buffer.
        """

    @abc.abstractmethod
    def make_variable_server(
        self,
        networks: Dict[str, Dict[str, snt.Module]],
    ) -> MavaVariableSource:
        """Create the variable server.
        Args:
            networks (Dict[str, Dict[str, snt.Module]]): dictionary with the
            system's networks in.
        Returns:
            variable_source (MavaVariableSource): A Mava variable source object.
        """

    @abc.abstractmethod
    def make_executor(
        self,
        networks: Dict[str, snt.Module],
        executor_networks: Dict[str, snt.Module],
        adder: Optional[adders.ParallelAdder] = None,
        variable_source: Optional[MavaVariableSource] = None,
    ) -> core.Executor:
        """Create an executor instance.
        Args:
            networks (Dict[str, snt.Module]): system networks.
            executor_networks (Dict[str, snt.Module]): executor networks for each agent in
                the system.
            adder (Optional[adders.ParallelAdder], optional): adder to send data to
                a replay buffer. Defaults to None.
            variable_source (Optional[core.VariableSource], optional): variables server.
                Defaults to None.
        Returns:
            core.Executor: system executor, a collection of agents making up the part
                of the system generating data by interacting the environment.
        """

    @abc.abstractmethod
    def make_trainer(
        self,
        networks: Dict[str, Dict[str, snt.Module]],
        dataset: Iterator[reverb.ReplaySample],
        variable_source: MavaVariableSource,
        trainer_networks: List[Any],
        trainer_table_entry: List[Any],
        logger: Optional[types.NestedLogger] = None,
    ) -> core.Trainer:
        """Create a trainer instance.

        Args:
            networks (Dict[str, Dict[str, snt.Module]]): system networks.
            dataset (Iterator[reverb.ReplaySample]): dataset iterator to feed data to
                the trainer networks.
            variable_source (MavaVariableSource): centralised variable source object.
            trainer_networks (List[Any]): list of networks to train.
            trainer_table_entry (List[Any]): tables associated with trainable networks.
            logger (Optional[types.NestedLogger], optional): Logger object for logging
                metadata. Defaults to None.
        Returns:
            core.Trainer: system trainer, that uses the collected data from the
                executors to update the parameters of the agent networks in the system.
        """


class OnlineSystemBuilder(SystemBuilder, SystemCallbackHookMixin):
    """Builder for systems which constructs individual components of the
    system."""

    def __init__(
        self,
        components: List[Callback] = [],
    ):
        """Initialise the system.
        Args:
            config (SystemConfig): system configuration specifying hyperparameters and
                additional information for constructing the system.
            extra_specs (Dict[str, Any], optional): defines the specifications of extra
                information used by the system. Defaults to {}.
        """
        self.callbacks = components

        self.on_building_init_start(self)
        self._agents = self._config.environment_spec.get_agent_ids()
        self._agent_types = self._config.environment_spec.get_agent_types()

        self.on_building_init_end(self)

    def make_replay_tables(
        self,
        environment_spec: specs.MAEnvironmentSpec,
    ) -> List[reverb.Table]:
        """ "Create tables to insert data into.
        Args:
            environment_spec (specs.MAEnvironmentSpec): description of the action and
                observation spaces etc. for each agent in the system.
        Raises:
            NotImplementedError: unknown executor type.
        Returns:
            List[reverb.Table]: a list of data tables for inserting data.
        """
        self._env_spec = environment_spec

        # start of make replay tables
        self.on_building_make_replay_table_start(self)

        # make adder signature
        self.on_building_adder_signature(self)

        # make rate limiter
        self.on_building_rate_limiter(self)

        # make tables
        self.on_building_make_tables(self)

        # end of make replay tables
        self.on_building_make_replay_table_end(self)

        return self.replay_tables

    def make_dataset_iterator(
        self,
        replay_client: reverb.Client,
        table_name: str,
    ) -> Iterator[reverb.ReplaySample]:
        """Create a dataset iterator to use for training/updating the system.
        Args:
            replay_client (reverb.Client): Reverb Client which points to the
                replay server.
        Returns:
            [type]: dataset iterator.
        Yields:
            Iterator[reverb.ReplaySample]: data samples from the dataset.
        """
        self._replay_client = replay_client
        self._table_name = table_name

        # start of make dataset iterator
        self.on_building_make_dataset_iterator_start(self)

        # make dataset
        self.on_building_dataset(self)

        # end of make dataset iterator
        self.on_building_make_dataset_iterator_end(self)

        return self.dataset

    def make_adder(
        self,
        replay_client: reverb.Client,
    ) -> Optional[adders.ParallelAdder]:
        """Create an adder which records data generated by the executor/environment.
        Args:
            replay_client (reverb.Client): Reverb Client which points to the
                replay server.
        Raises:
            NotImplementedError: unknown executor type.
        Returns:
            Optional[adders.ParallelAdder]: adder which sends data to a replay buffer.
        """
        self._replay_client = replay_client

        # start of make make adder
        self.on_building_make_adder_start(self)

        # make adder signature
        self.on_building_adder_priority(self)

        # make rate limiter
        self.on_building_make_adder(self)

        # end of make make adder
        self.on_building_make_adder_end(self)

        return self.adder

    def make_variable_server(
        self,
        networks: Dict[str, Dict[str, snt.Module]],
    ) -> MavaVariableSource:
        """Create the variable server.
        Args:
            networks (Dict[str, Dict[str, snt.Module]]): dictionary with the
            system's networks in.
        Returns:
            variable_source (MavaVariableSource): A Mava variable source object.
        """
        self._networks = networks

        # start of make variable server
        self.on_building_make_variable_server_start(self)

        # make variable server
        self.on_building_variable_server(self)

        # end of make variable server
        self.on_building_make_variable_server_end(self)

        return self.variable_server

    def make_executor(
        self,
        networks: Dict[str, snt.Module],
        policy_networks: Dict[str, snt.Module],
        adder: Optional[adders.ParallelAdder] = None,
        variable_source: Optional[MavaVariableSource] = None,
    ) -> core.Executor:
        """Create an executor instance.
        Args:
            networks (Dict[str, snt.Module]): system networks.
            executor_networks (Dict[str, snt.Module]): executor networks for each agent in
                the system.
            adder (Optional[adders.ParallelAdder], optional): adder to send data to
                a replay buffer. Defaults to None.
            variable_source (Optional[core.VariableSource], optional): variables server.
                Defaults to None.
        Returns:
            core.Executor: system executor, a collection of agents making up the part
                of the system generating data by interacting the environment.
        """
        self._networks = networks
        self._policy_networks = policy_networks
        self._adder = adder
        self._variable_source = variable_source

        # start of make executor
        self.on_building_make_executor_start(self)

        # make variable client
        self.on_building_executor_variable_client(self)

        # make executor
        self.on_building_executor(self)

        # end of make executor
        self.on_building_make_executor_end(self)

        return self.executor

    def make_trainer(
        self,
        networks: Dict[str, Dict[str, snt.Module]],
        dataset: Iterator[reverb.ReplaySample],
        variable_source: MavaVariableSource,
        trainer_networks: List[Any],
        trainer_table_entry: List[Any],
        logger: Optional[types.NestedLogger] = None,
    ) -> core.Trainer:
        """Create a trainer instance.
        Args:
            networks (Dict[str, Dict[str, snt.Module]]): system networks.
            dataset (Iterator[reverb.ReplaySample]): dataset iterator to feed data to
                the trainer networks.
            variable_source (MavaVariableSource): centralised variable source object.
            trainer_networks (List[Any]): list of networks to train.
            trainer_table_entry (List[Any]): tables associated with trainable networks.
            logger (Optional[types.NestedLogger], optional): Logger object for logging
                metadata. Defaults to None.
        Returns:
            core.Trainer: system trainer, that uses the collected data from the
                executors to update the parameters of the agent networks in the system.
        """
        self._networks = networks
        self._dataset = dataset
        self._variable_source = variable_source
        self._trainer_networks = trainer_networks
        self._trainer_table_entry = trainer_table_entry
        self._logger = logger

        # start of make trainer
        self.on_building_make_trainer_start(self)

        # make variable client
        self.on_building_trainer_variable_client(self)

        # make trainer
        self.on_building_trainer(self)

        # make statistics tracker
        self.on_building_trainer_statistics(self)

        # end of make trainer
        self.on_building_make_trainer_end(self)

        return self.trainer
