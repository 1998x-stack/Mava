import os
import time
from typing import Any, Dict, Sequence, Union

import numpy as np
from acme.tf import utils as tf2_utils

from mava.systems.tf import savers as tf2_savers


class VariableSource:
    def __init__(
        self, variables: Dict[str, Any], checkpoint: bool, checkpoint_subpath: str
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
        # Init the variable dictionary
        self.variables = variables

        if checkpoint:
            # Only save variables that are not empty.
            save_variables = {}
            for key in self.variables.keys():
                var = self.variables[key]
                # Don't store empty tuple (e.g. empty observation_network) variables
                if not (type(var) == tuple and len(var) == 0):
                    save_variables[key] = variables[key]

            # Create checkpointer
            subdir = os.path.join("variable_source")
            self._system_checkpointer = tf2_savers.Checkpointer(
                time_delta_minutes=15,
                directory=checkpoint_subpath,
                objects_to_save=save_variables,
                subdirectory=subdir,
            )

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
        if type(names) == str:
            return self.variables[names]  # type: ignore
        else:
            variables: Dict[str, Dict[str, np.ndarray]] = {}
            for var_key in names:
                # TODO (dries): Do we really have to convert the variables to
                # numpy each time. Can we not keep the variables in numpy form
                # without the checkpointer complaining?
                variables[var_key] = tf2_utils.to_numpy(self.variables[var_key])
            return variables

    def set_variables(self, names: Sequence[str], vars: Dict[str, np.ndarray]) -> None:
        """Set variables in the variable source.
        Args:
            names (Union[str, Sequence[str]]): Names of the variables to set.
            vars(Dict[str, np.ndarray]): The values to set the variables to.
        Returns:
            None
        """
        if type(names) == str:
            vars = {names: vars}  # type: ignore
            names = [names]  # type: ignore

        for var_key in names:
            assert var_key in self.variables
            if type(self.variables[var_key]) == tuple:
                # Loop through tuple
                for var_i in range(len(self.variables[var_key])):
                    self.variables[var_key][var_i].assign(vars[var_key][var_i])
            else:
                self.variables[var_key].assign(vars[var_key])
        return

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
        if type(names) == str:
            vars = {names: vars}  # type: ignore
            names = [names]  # type: ignore

        for var_key in names:
            assert var_key in self.variables
            # Note: Can also use self.variables[var_key] = /
            # self.variables[var_key] + vars[var_key]
            self.variables[var_key].assign_add(vars[var_key])
        return

    def run(self) -> None:
        """Run the variable source. This function allows for
        checkpointing and other centralised computations to
        be performed by the variable source.
                Args:
                    None
                Returns:
                    None
        """
        # Checkpoints every 15 minutes
        while True:
            time.sleep(15 * 60)
            if self._system_checkpointer:
                self._system_checkpointer.save()
                print("Updated variables checkpoint.")