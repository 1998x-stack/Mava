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

"""Commonly used adder components for system builders"""

from mava.callbacks import Callback
from mava.core import SystemExecutor


class Observer(Callback):
    def on_execution_observe_first(self, executor: SystemExecutor) -> None:
        if executor._adder:
            executor._adder.add_first(executor._timestep, executor._extras)

    def on_execution_observe(self, executor: SystemExecutor) -> None:
        if executor._adder:
            executor._adder.add(
                executor._actions, executor._next_timestep, executor._next_extras
            )