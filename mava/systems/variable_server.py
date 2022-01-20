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

"""Mava variable server implementation."""


from typing import Dict, Sequence, Union, List

import numpy as np

from mava.core import SystemVariableServer
from mava.callbacks import Callback
from mava.callbacks import CallbackHookMixin
from mava.utils.training_utils import non_blocking_sleep


class VariableServer(SystemVariableServer, CallbackHookMixin):
    def __init__(
        self,
        components: List[Callback],
    ) -> None:
        """Initialise the variable source
        Args:
            variables (Dict[str, Any]): a dictionary with
            variables which should be stored in it.
            checkpoint (bool): Indicates whether checkpointing should be performed.
            checkpoint_subpath (str): checkpoint path
        Returns:
            None
        """
        self.callbacks = components

        self.on_variables_init_start()

        self.on_variables_init()

        self.on_variables_checkpoint()

        self.on_variables_init_end()

    def get_variables(
        self, names: Union[str, Sequence[str]]
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """Get variables from the variable source.
        Args:
            names (Union[str, Sequence[str]]): Names of the variables to get.
        Returns:
            variables(Dict[str, Dict[str, np.ndarray]]): The variables that
            were requested.
        """
        self._names = names

        self.on_variables_get_server_variables_start()

        self.on_variables_get_server_variables()

        self.on_variables_get_server_variables_end()

    def set_variables(self, names: Sequence[str], vars: Dict[str, np.ndarray]) -> None:
        """Set variables in the variable source.
        Args:
            names (Union[str, Sequence[str]]): Names of the variables to set.
            vars(Dict[str, np.ndarray]): The values to set the variables to.
        Returns:
            None
        """
        self._names = names
        self._vars = vars

        self.on_variables_set_server_variables_start()

        self.on_variables_set_server_variables()

        self.on_variables_set_server_variables_end()

    def add_to_variables(
        self, names: Sequence[str], vars: Dict[str, np.ndarray]
    ) -> None:
        """Add to the variables in the variable source.
        Args:
            names (Union[str, Sequence[str]]): Names of the variables to add to.
            vars(Dict[str, np.ndarray]): The values to add to the variables to.
        Returns:
            None
        """
        self._names = names
        self._vars = vars

        self.on_variables_add_to_server_variables_start()

        self.on_variables_add_to_server_variables()

        self.on_variables_add_to_server_variables_end()

    def run(self) -> None:
        """Run the variable source. This function allows for
        checkpointing and other centralised computations to
        be performed by the variable source.
                Args:
                    None
                Returns:
                    None
        """

        self.on_variables_run_server_start()

        # Checkpoints every 5 minutes
        while True:
            # Wait 10 seconds before checking again
            non_blocking_sleep(10)

            # Add 1 extra second just to make sure that the checkpointer
            # is ready to save.
            self.on_building_variable_run_server_loop_start()

            self.on_variables_run_server_loop_checkpoint()

            self.on_variables_run_server_loop()

            self.on_variables_run_server_loop_termination()

            self.on_building_variable_run_server_loop_end()
