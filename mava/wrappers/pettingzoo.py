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

"""Wraps a PettingZoo MARL environment to be used as a dm_env environment."""
from typing import Any, Dict, Iterator, List, Optional, Union

import dm_env
import numpy as np
from acme import specs
from acme.wrappers.gym_wrapper import _convert_to_spec
from pettingzoo.utils.env import AECEnv, ParallelEnv
from supersuit import black_death_v1, pad_action_space_v0, pad_observations_v0

from mava import types
from mava.utils.wrapper_utils import (
    apply_env_wrapper_preprocessers,
    convert_np_type,
    parameterized_restart,
)
from mava.wrappers.env_wrappers import ParallelEnvWrapper, SequentialEnvWrapper


# TODO(Kale-ab): Check usage agents vs possible agents
class PettingZooAECEnvWrapper(SequentialEnvWrapper):
    """Environment wrapper for PettingZoo MARL environments."""

    # Note: we don't inherit from base.EnvironmentWrapper because that class
    # assumes that the wrapped environment is a dm_env.Environment.
    def __init__(
        self,
        environment: AECEnv,
        env_preprocess_wrappers: Optional[List] = [
            # (env_preprocessor, dict_with_preprocessor_params)
            (black_death_v1, None),
            (pad_action_space_v0, None),
            (pad_observations_v0, None),
        ],
    ):
        self._environment = environment
        self._reset_next_step = True

        if env_preprocess_wrappers:
            self._environment = apply_env_wrapper_preprocessers(
                self._environment, env_preprocess_wrappers
            )

    def reset(self) -> dm_env.TimeStep:
        """Resets the episode."""
        self._reset_next_step = False
        self._environment.reset()
        self._step_type = dm_env.StepType.FIRST

        observe, _, done, _ = self._environment.last()
        agent = self.current_agent
        observation = self._convert_observation(agent, observe, done)

        self._discount = convert_np_type(
            self.discount_spec()[agent].dtype, 1
        )  # Not used in pettingzoo
        reward = convert_np_type(self.reward_spec()[agent].dtype, 0)
        return parameterized_restart(reward, self._discount, observation)

    def step(self, action: Union[int, float]) -> dm_env.TimeStep:
        """Steps the environment."""
        if self._reset_next_step:
            return self.reset()

        observe, reward, done, info = self._environment.last()

        # If current agent is done
        if done:
            self._environment.step(None)
            self._step_type = dm_env.StepType.LAST
        else:
            self._environment.step(action)
            self._step_type = dm_env.StepType.MID

            # Update these vars so dm_env.TimeStep returned has
            # the last information.
            observe, reward, done, info = self._environment.last()

        agent = self.current_agent
        # Convert rewards to match spec
        reward = convert_np_type(self.reward_spec()[agent].dtype, reward)
        observation = self._convert_observation(agent, observe, done)

        # Reset if all agents are done
        if self.env_done():
            self._reset_next_step = True

        return dm_env.TimeStep(
            observation=observation,
            reward=reward,
            discount=self._discount,
            step_type=self._step_type,
        )

    def env_done(self) -> bool:
        return self._environment.env_done

    def agent_iter(self, max_iter: int = 2 ** 63) -> Iterator:
        return self._environment.agent_iter(max_iter)

    # Convert PettingZoo observation so it's dm_env compatible. Also, the list
    # of legal actions must be converted to a legal actions mask.
    def _convert_observation(
        self, agent: str, observe: Union[dict, np.ndarray], done: bool
    ) -> types.OLT:
        if isinstance(observe, dict) and "action_mask" in observe:
            legals = observe["action_mask"]
            observe = observe["observation"]
        else:
            legals = np.ones(
                _convert_to_spec(self._environment.action_spaces[agent]).shape,
                dtype=self._environment.action_spaces[agent].dtype,
            )
        observation = types.OLT(
            observation=observe,
            legal_actions=legals,
            terminal=np.asarray([done], dtype=np.float32),
        )
        return observation

    def observation_spec(self) -> types.Observation:
        observation_specs = {}
        for agent in self._environment.possible_agents:
            observation_specs[agent] = types.OLT(
                observation=_convert_to_spec(
                    self._environment.observation_spaces[agent]
                ),
                legal_actions=_convert_to_spec(self._environment.action_spaces[agent]),
                terminal=specs.Array((1,), np.float32),
            )
        return observation_specs

    def action_spec(self) -> Dict[str, specs.DiscreteArray]:
        action_specs = {}
        for agent in self._environment.possible_agents:
            action_specs[agent] = _convert_to_spec(
                self._environment.action_spaces[agent]
            )
        return action_specs

    def reward_spec(self) -> Dict[str, specs.Array]:
        reward_specs = {}
        for agent in self._environment.possible_agents:
            reward_specs[agent] = specs.Array((), np.float32)

        return reward_specs

    def discount_spec(self) -> Dict[str, specs.BoundedArray]:
        discount_specs = {}
        for agent in self._environment.possible_agents:
            discount_specs[agent] = specs.BoundedArray(
                (), np.float32, minimum=0, maximum=1.0
            )
        return discount_specs

    def extra_spec(self) -> Dict[str, specs.BoundedArray]:
        return {}

    def seed(self, seed: int = None) -> None:
        self._environment.seed(seed)

    @property
    def agents(self) -> List:
        return self._environment.agents

    @property
    def possible_agents(self) -> List:
        return self._environment.possible_agents

    @property
    def environment(self) -> AECEnv:
        """Returns the wrapped environment."""
        return self._environment

    @property
    def current_agent(self) -> Any:
        return self._environment.agent_selection

    def __getattr__(self, name: str) -> Any:
        """Expose any other attributes of the underlying environment."""
        return getattr(self._environment, name)


class PettingZooParallelEnvWrapper(ParallelEnvWrapper):
    """Environment wrapper for PettingZoo MARL environments."""

    # Note: we don't inherit from base.EnvironmentWrapper because that class
    # assumes that the wrapped environment is a dm_env.Environment.
    def __init__(
        self,
        environment: ParallelEnv,
        env_preprocess_wrappers: Optional[List] = [
            # (env_preprocessor, dict_with_preprocessor_params)
            (black_death_v1, None),
            (pad_action_space_v0, None),
            (pad_observations_v0, None),
        ],
    ):
        self._environment = environment
        self._reset_next_step = True

        if env_preprocess_wrappers:
            self._environment = apply_env_wrapper_preprocessers(
                self._environment, env_preprocess_wrappers
            )

    def reset(self) -> dm_env.TimeStep:
        """Resets the episode."""
        self._reset_next_step = False
        self._step_type = dm_env.StepType.FIRST
        discount_spec = self.discount_spec()
        self._discounts = {
            agent: convert_np_type(discount_spec[agent].dtype, 1)
            for agent in self._environment.possible_agents
        }
        observe = self._environment.reset()
        observations = self._convert_observations(
            observe, {agent: False for agent in self.possible_agents}
        )
        rewards_spec = self.reward_spec()
        rewards = {
            agent: convert_np_type(rewards_spec[agent].dtype, 0)
            for agent in self.possible_agents
        }

        discount_spec = self.discount_spec()
        self._discounts = {
            agent: convert_np_type(discount_spec[agent].dtype, 1)
            for agent in self.possible_agents
        }
        return parameterized_restart(rewards, self._discounts, observations)

    def step(self, actions: Dict[str, np.ndarray]) -> dm_env.TimeStep:
        """Steps the environment."""

        if self._reset_next_step:
            return self.reset()

        observations, rewards, dones, infos = self._environment.step(actions)

        rewards_spec = self.reward_spec()
        #  Handle empty rewards
        if not rewards:
            rewards = {
                agent: convert_np_type(rewards_spec[agent].dtype, 0)
                for agent in self.possible_agents
            }
        else:
            rewards = {
                agent: convert_np_type(rewards_spec[agent].dtype, reward)
                for agent, reward in rewards.items()
            }

        if observations:
            observations = self._convert_observations(observations, dones)

        if self.env_done():
            self._step_type = dm_env.StepType.LAST
            self._reset_next_step = True
        else:
            self._step_type = dm_env.StepType.MID

        return dm_env.TimeStep(
            observation=observations,
            reward=rewards,
            discount=self._discounts,
            step_type=self._step_type,
        )

    def env_done(self) -> bool:
        return self._environment.env_done

    # Convert PettingZoo observation so it's dm_env compatible. Also, the list
    # of legal actions must be converted to a legal actions mask.
    def _convert_observations(
        self, observes: Dict[str, np.ndarray], dones: Dict[str, bool]
    ) -> types.Observation:
        observations: Dict[str, types.OLT] = {}
        for agent, observation in observes.items():
            if isinstance(observation, dict) and "action_mask" in observation:
                legals = observation["action_mask"]
                observation = observation["observation"]
            else:
                # TODO Handle legal actions better for continous envs,
                #  maybe have min and max for each action and clip the agents actions
                #  accordingly
                legals = np.ones(
                    _convert_to_spec(self._environment.action_spaces[agent]).shape,
                    dtype=self._environment.action_spaces[agent].dtype,
                )
            observations[agent] = types.OLT(
                observation=observation,
                legal_actions=legals,
                terminal=np.asarray([dones[agent]], dtype=np.float32),
            )

        return observations

    def observation_spec(self) -> types.Observation:
        observation_specs = {}
        for agent in self._environment.possible_agents:
            observation_specs[agent] = types.OLT(
                observation=_convert_to_spec(
                    self._environment.observation_spaces[agent]
                ),
                legal_actions=_convert_to_spec(self._environment.action_spaces[agent]),
                terminal=specs.Array((1,), np.float32),
            )
        return observation_specs

    def action_spec(self) -> Dict[str, Union[specs.DiscreteArray, specs.BoundedArray]]:
        action_specs = {}
        action_spaces = self._environment.action_spaces
        for agent in self._environment.possible_agents:
            action_specs[agent] = _convert_to_spec(action_spaces[agent])
        return action_specs

    def reward_spec(self) -> Dict[str, specs.Array]:
        reward_specs = {}
        for agent in self._environment.possible_agents:
            reward_specs[agent] = specs.Array((), np.float32)

        return reward_specs

    def discount_spec(self) -> Dict[str, specs.BoundedArray]:
        discount_specs = {}
        for agent in self._environment.possible_agents:
            discount_specs[agent] = specs.BoundedArray(
                (), np.float32, minimum=0, maximum=1.0
            )
        return discount_specs

    def extra_spec(self) -> Dict[str, specs.BoundedArray]:
        return {}

    def seed(self, seed: int = None) -> None:
        self._environment.seed(seed)

    @property
    def agents(self) -> List:
        return self._environment.agents

    @property
    def possible_agents(self) -> List:
        return self._environment.possible_agents

    @property
    def environment(self) -> ParallelEnv:
        """Returns the wrapped environment."""
        return self._environment

    @property
    def current_agent(self) -> Any:
        return self._environment.agent_selection

    def __getattr__(self, name: str) -> Any:
        """Expose any other attributes of the underlying environment."""
        return getattr(self._environment, name)
