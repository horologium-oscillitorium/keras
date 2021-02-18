# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
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
# ==============================================================================

import tensorflow as tf
"""Strategy combinations for combinations.combine()."""


multidevice_strategies = [
    tf.compat.v2.__internal__.distribute.combinations.mirrored_strategy_with_gpu_and_cpu,
    tf.compat.v2.__internal__.distribute.combinations.mirrored_strategy_with_two_gpus,
    tf.compat.v2.__internal__.distribute.combinations.tpu_strategy,
]

multiworker_strategies = [
    tf.compat.v2.__internal__.distribute.combinations.multi_worker_mirrored_2x1_cpu,
    tf.compat.v2.__internal__.distribute.combinations.multi_worker_mirrored_2x1_gpu,
    tf.compat.v2.__internal__.distribute.combinations.multi_worker_mirrored_2x2_gpu
]

strategies_minus_default_minus_tpu = [
    tf.compat.v2.__internal__.distribute.combinations.one_device_strategy,
    tf.compat.v2.__internal__.distribute.combinations.one_device_strategy_gpu,
    tf.compat.v2.__internal__.distribute.combinations.mirrored_strategy_with_gpu_and_cpu,
    tf.compat.v2.__internal__.distribute.combinations.mirrored_strategy_with_two_gpus,
    tf.compat.v2.__internal__.distribute.combinations.central_storage_strategy_with_gpu_and_cpu
]

strategies_minus_tpu = [
    tf.compat.v2.__internal__.distribute.combinations.default_strategy,
    tf.compat.v2.__internal__.distribute.combinations.one_device_strategy,
    tf.compat.v2.__internal__.distribute.combinations.one_device_strategy_gpu,
    tf.compat.v2.__internal__.distribute.combinations.mirrored_strategy_with_gpu_and_cpu,
    tf.compat.v2.__internal__.distribute.combinations.mirrored_strategy_with_two_gpus,
    tf.compat.v2.__internal__.distribute.combinations.central_storage_strategy_with_gpu_and_cpu
]

multi_worker_mirrored_strategies = [
    tf.compat.v2.__internal__.distribute.combinations.multi_worker_mirrored_2x1_cpu,
    tf.compat.v2.__internal__.distribute.combinations.multi_worker_mirrored_2x1_gpu,
    tf.compat.v2.__internal__.distribute.combinations.multi_worker_mirrored_2x2_gpu,
]

tpu_strategies = [
    tf.compat.v2.__internal__.distribute.combinations.tpu_strategy,
]

all_strategies = strategies_minus_tpu + tpu_strategies
