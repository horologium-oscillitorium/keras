# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
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
"""Test multi-worker Keras."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow.compat.v2 as tf

import collections
import copy
import functools
import json
import os
import sys
import threading

from absl.testing import parameterized

# pylint: disable=g-direct-tensorflow-import
import keras
from tensorflow.python.distribute import distribute_coordinator as dc
from tensorflow.python.distribute import multi_worker_test_base as test_base
from keras import backend
from keras import callbacks
from keras import metrics as metrics_module
from keras import models
from keras import optimizer_v1
from keras.distribute import multi_worker_testing_utils


def _clone_and_build_model(model, strategy):
  # The new "original" model in worker 0.
  with strategy.scope():
    cloned_model = models.clone_model(model)

  # Compile and build model.
  if isinstance(model.optimizer, optimizer_v1.TFOptimizer):
    optimizer = model.optimizer
    # TODO(yuefengz): figure out why the optimizer here is still a
    # TFOptimizer.
    while isinstance(optimizer, optimizer_v1.TFOptimizer):
      optimizer = optimizer.optimizer
    optimizer = copy.deepcopy(optimizer)
  else:
    optimizer_config = model.optimizer.get_config()
    optimizer = type(model.optimizer).from_config(optimizer_config)

  cloned_model.compile(
      optimizer,
      model.loss,
      metrics=metrics_module.clone_metrics(model._compile_metrics),
      loss_weights=model.loss_weights,
      sample_weight_mode=model.sample_weight_mode,
      weighted_metrics=metrics_module.clone_metrics(
          model._compile_weighted_metrics))
  return cloned_model


# TODO(b/123918215): Possibly merge this Callback with keras_test.Counter.
class MultiWorkerVerificationCallback(callbacks.Callback):
  """MultiWorkerVerificationCallback verifies the callbacks in multi-worker scheme.

  This Callback is intended to be used for verifying the callback is indeed
  called the correct number of times in various task types.

  Attributes:
    _task_dict: A nested dictionary storing the number of times a callback has
                been called in specific task type, task index, and method name.
                Look up structure is
                task_name -> task_id -> tracking_method_name -> invoke_count
                For example, a _task_dict of
                {
                    'ps': {
                         0: {
                             'on_epoch_begin': 2
                         },
                         1: {
                             'on_epoch_begin': 2
                         }
                    },
                    'worker': {
                         0: {
                             'on_epoch_begin': 2
                         },
                         1: {
                             'on_epoch_begin': 2
                         }
                    }
                }
                indicates the ps task has 'on_epoch_begin' called twice on each
                of the two indices, and likewise for worker task.
  """

  # TODO(rchao): Add other method calls to verify.
  METHODS_TO_VERIFY = ['on_epoch_begin']

  def __init__(self, num_epoch, num_worker):
    """Initialize a MultiWorkerVerificationCallback.

    Args:
      num_epoch: Number of epochs this Callback is expected to be called for.
      num_worker: Number of workers this Callback is expected to be called from.
    """
    super(MultiWorkerVerificationCallback, self).__init__()
    self._num_epoch = num_epoch
    self._num_worker = num_worker
    self._task_dict = {
        key: collections.defaultdict(lambda: collections.defaultdict(int))
        for key in ['ps', 'worker']
    }
    self._lock = threading.Lock()
    self._is_between_graph = None
    self.wrap_methods(self.METHODS_TO_VERIFY)

  @property
  def is_between_graph(self):
    return self._is_between_graph

  @is_between_graph.setter
  def is_between_graph(self, is_between_graph):
    self._is_between_graph = is_between_graph

  def wrap_methods(self, method_names):
    """Wrap methods so that the counts of calls are tracked.

    Args:
      method_names: A list of names of methods to track calls.
    """
    for method_name in method_names:
      method = getattr(self, method_name)

      def wrapped_method(method_to_wrap, name, *arg, **kwargs):
        # Use lock to ensure += operation is thread-safe.
        with self._lock:
          task_config = json.loads(os.environ['TF_CONFIG'])['task']
          self._task_dict[task_config['type']][task_config['index']][name] += 1
        method_to_wrap(*arg, **kwargs)

      setattr(self, method_name,
              functools.partial(wrapped_method, method, method_name))

  def verify(self, test_case):
    method_count_dict = {
        method_name: self._num_epoch for method_name in self.METHODS_TO_VERIFY
    }
    assert self._is_between_graph is not None
    if self._is_between_graph:
      # TODO(b/124171024): In between-graph replication, by default only the
      # chief calls callback. Fix this test to cover that, as well as the rare
      # cases where all workers call.
      worker_call_count = {
          i: method_count_dict for i in range(0, self._num_worker)
      }
    else:
      # If in-graph, only the first worker calls callback methods.
      worker_call_count = {0: method_count_dict}
    test_case.assertDictEqual(
        self._task_dict,
        {
            # PS' callback is not supposed to be called.
            'ps': {},
            # Each of the Worker should be called num_epoch of times.
            'worker': worker_call_count
        })


class KerasMultiWorkerTestIndependentWorker(test_base.IndependentWorkerTestBase,
                                            parameterized.TestCase):

  @tf.__internal__.distribute.combinations.generate(
      tf.__internal__.test.combinations.combine(
          mode=['graph'],
          strategy_cls=[
              tf.distribute.MultiWorkerMirroredStrategy,
          ],
          required_gpus=[0, 1]))
  def testSimpleModelIndependentWorkerSync(self, strategy_cls):
    num_workers = 2
    num_epoch = 2

    cluster_spec = tf.__internal__.distribute.multi_process_runner.create_cluster_spec(num_workers=num_workers)
    self._barrier = dc._Barrier(2)

    # The verification callback will be shared by multiple threads.
    verification_callback = MultiWorkerVerificationCallback(
        num_epoch=num_epoch, num_worker=num_workers)

    def _independent_worker_fn(*args, **kwargs):  # pylint: disable=unused-argument
      """Simulates an Independent Worker inside of a thread."""
      with tf.compat.v1.test.mock.patch.object(dc, '_run_std_server',
                                  self._make_mock_run_std_server()):
        strategy = strategy_cls()
        verification_callback.is_between_graph = \
            strategy.extended.experimental_between_graph
        batch_size = 64
        steps = 2
        train_ds, _ = multi_worker_testing_utils.mnist_synthetic_dataset(
            batch_size, steps)
        with strategy.scope():
          model = multi_worker_testing_utils.get_mnist_model((28, 28, 1))
        orig_loss, _ = model.evaluate(train_ds, steps=steps)
        callbacks_for_fit = tf.nest.flatten(
            kwargs.get('verification_callback', []))
        history = model.fit(
            x=train_ds,
            epochs=num_epoch,
            steps_per_epoch=steps,
            callbacks=callbacks_for_fit)
        self.assertIsInstance(history, keras.callbacks.History)
        trained_loss, _ = model.evaluate(train_ds, steps=steps)
        self.assertLess(trained_loss, orig_loss)

    threads = self.run_multiple_tasks_in_threads(
        _independent_worker_fn,
        cluster_spec,
        verification_callback=verification_callback)

    threads_to_join = []
    strategy = strategy_cls()
    if strategy.extended.experimental_between_graph:
      for ts in threads.values():
        threads_to_join.extend(ts)
    else:
      threads_to_join = [threads['worker'][0]]
    self.join_independent_workers(threads_to_join)
    verification_callback.verify(self)


if __name__ == '__main__':
  # Enable manual variable initialization to make sure variables are initialized
  # by `init_restore_or_wait_for_variables`.
  backend.manual_variable_initialization(True)
  with tf.compat.v1.test.mock.patch.object(sys, 'exit', os._exit):
    tf.test.main()
