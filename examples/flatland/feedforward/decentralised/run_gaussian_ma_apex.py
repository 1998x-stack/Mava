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


import functools
from datetime import datetime
from typing import Any, Dict

import launchpad as lp
import sonnet as snt
from absl import app, flags

from mava import specs as mava_specs
from mava.components.tf.modules.exploration.exploration_scheduling import (
    gaussian_ma_apex_exploration_scheduler,
)
from mava.systems.tf import madqn
from mava.utils import lp_utils
from mava.utils.environments.flatland_utils import flatland_env_factory
from mava.utils.loggers import logger_utils
from mava.wrappers.environment_loop_wrappers import MonitorParallelEnvironmentLoop

FLAGS = flags.FLAGS

epsilon = 0.4
alpha = 7.0
sigma_coeff = 0.5

# epsilons = [0.2, 0.3, 0.4, 0.5, 0.6]
# alphas = [5.0, 6.0, 7.0, 8.0, 9.0]
# sigma_coeffs = [0.3, 0.4, 0.5, 0.7, 0.9]
# epsilon = np.random.choice(epsilons)
# alpha = np.random.choice(alphas)
# sigma_coeff = np.random.choice(sigma_coeffs)

flags.DEFINE_string(
    "mava_id",
    "gaussian-apex-epsilon={:.2f}-alpha={:.2f}-sigma_coeff={:.2f}-".format(
        epsilon, alpha, sigma_coeff
    )
    + str(datetime.now()),
    "Experiment identifier that can be used to continue experiments.",
)
flags.DEFINE_string("base_dir", "./logs", "Base dir to store experiments.")

flatland_env_config: Dict = {
    "n_agents": 3,
    "x_dim": 30,
    "y_dim": 30,
    "n_cities": 2,
    "max_rails_between_cities": 2,
    "max_rails_in_city": 3,
    "seed": 0,
    "malfunction_rate": 1 / 200,
    "malfunction_min_duration": 20,
    "malfunction_max_duration": 50,
    "observation_max_path_depth": 30,
    "observation_tree_depth": 2,
}


def main(_: Any) -> None:
    """Run program

    Args:
        _ (Any): Arguments
    """

    # Environment.
    environment_factory = functools.partial(
        flatland_env_factory, env_config=flatland_env_config
    )

    # Environment Spec
    environment_spec = mava_specs.MAEnvironmentSpec(
        environment_factory(evaluation=False)  # type:ignore
    )

    # Agent ids
    agents = environment_spec.get_agent_ids()

    # Networks.
    network_factory = lp_utils.partial_kwargs(
        madqn.make_default_networks, policy_networks_layer_sizes=(128, 128)
    )

    # Checkpointer appends "Checkpoints" to checkpoint_dir
    checkpoint_dir = f"{FLAGS.base_dir}/{FLAGS.mava_id}"

    # Log every [log_every] seconds.
    log_every = 10
    logger_factory = functools.partial(
        logger_utils.make_logger,
        directory=FLAGS.base_dir,
        to_terminal=True,
        to_tensorboard=True,
        time_stamp=FLAGS.mava_id,
        time_delta=log_every,
    )

    num_executors = 8
    exploration_scheduler_fn = gaussian_ma_apex_exploration_scheduler(
        agent_ids=agents,
        num_executors=num_executors,
        epsilon=epsilon,
        alpha=alpha,
        sigma_coeff=sigma_coeff,
    )

    # distributed program
    program = madqn.MADQN(
        environment_factory=environment_factory,
        network_factory=network_factory,
        logger_factory=logger_factory,
        num_executors=num_executors,
        exploration_scheduler_fn=exploration_scheduler_fn,
        optimizer=snt.optimizers.Adam(learning_rate=1e-4),
        max_executor_steps=300_000,
        checkpoint_subpath=checkpoint_dir,
        eval_loop_fn=MonitorParallelEnvironmentLoop,
        eval_loop_fn_kwargs={"path": checkpoint_dir, "record_every": 1},
    ).build()

    # Ensure only trainer runs on gpu, while other processes run on cpu.
    local_resources = lp_utils.to_device(
        program_nodes=program.groups.keys(), nodes_on_gpu=["trainer"]
    )

    # Launch.
    lp.launch(
        program,
        lp.LaunchType.LOCAL_MULTI_PROCESSING,
        terminal="current_terminal",
        local_resources=local_resources,
    )


if __name__ == "__main__":
    app.run(main)
