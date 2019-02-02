import os
import numpy as np
import tensorflow as tf


def base(features, labels, mode, params):
    model = FullyConnectedNetwork()
    logits = model(features)
    predictions = tf.argmax(logits, axis=1)

    if mode == tf.estimator.ModeKeys.PREDICT:
        softmax_layer = tf.keras.layers.Softmax()
        probabilities = softmax_layer(logits)
        return tf.estimator.EstimatorSpec(mode, predictions={'predictions': predictions, 'probabilities': probabilities})

    one_hot_labels = tf.one_hot(labels, 10)
    loss = tf.losses.softmax_cross_entropy(one_hot_labels, logits)

    if mode == tf.estimator.ModeKeys.EVAL:
        accuracy = tf.metrics.accuracy(labels, predictions)
        return tf.estimator.EstimatorSpec(mode, loss=loss, eval_metric_ops={'accuracy': accuracy})

    opt = tf.train.GradientDescentOptimizer(learning_rate=params['learning_rate'])

    train_op = opt.minimize(loss, global_step=tf.train.get_global_step())

    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)


def multi(features, labels, mode, params):
    model = FullyConnectedNetwork()
    logits = model(features)
    predictions = tf.argmax(logits, axis=1)

    if mode == tf.estimator.ModeKeys.PREDICT:
        softmax_layer = tf.keras.layers.Softmax()
        probabilities = softmax_layer(logits)
        return tf.estimator.EstimatorSpec(mode, predictions={'predictions': predictions, 'probabilities': probabilities})

    one_hot_labels = tf.one_hot(labels, 10)
    loss = tf.losses.softmax_cross_entropy(one_hot_labels, logits)

    if mode == tf.estimator.ModeKeys.EVAL:
        accuracy = tf.metrics.accuracy(labels, predictions)
        return tf.estimator.EstimatorSpec(mode, loss=loss, eval_metric_ops={'accuracy': accuracy})

    opt = tf.train.GradientDescentOptimizer(learning_rate=params['learning_rate'])

    train_op = opt.minimize(loss, global_step=tf.train.get_global_step())

    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)


def ewc(features, labels, mode, params):
    model = FullyConnectedNetwork()
    logits = model(features)
    predictions = tf.argmax(logits, axis=1)
    one_hot_labels = tf.one_hot(labels, 10)

    if mode == tf.estimator.ModeKeys.PREDICT:
        softmax_layer = tf.keras.layers.Softmax()
        probabilities = softmax_layer(logits)
        return tf.estimator.EstimatorSpec(mode, predictions={'predictions': predictions, 'probabilities': probabilities})

    loss = tf.losses.softmax_cross_entropy(one_hot_labels, logits)

    checkpoint = params['model_dir']
    if os.path.isdir(checkpoint):
        for weight in model.weights:
            name = weight.name[:-2]
            cur_var = weight
            pre_var = tf.train.load_variable(checkpoint, name)
            fisher = tf.train.load_variable(checkpoint, name+'/fisher')

            ewc_loss = tf.losses.mean_squared_error(cur_var, pre_var, fisher)
            loss = loss + ewc_loss

    if mode == tf.estimator.ModeKeys.EVAL:
        accuracy = tf.metrics.accuracy(labels, predictions)
        return tf.estimator.EstimatorSpec(mode, loss=loss, eval_metric_ops={'accuracy': accuracy})

    opt = tf.train.GradientDescentOptimizer(learning_rate=params['learning_rate'])

    grads_and_vars = opt.compute_gradients(loss)
    fisher_hook = []
    for grad_and_var in grads_and_vars:
        fisher_hook.append(GradientAccumulationHook(grad_and_var))

    train_op = opt.apply_gradients(grads_and_vars, global_step=tf.train.get_global_step())

    return tf.estimator.EstimatorSpec(mode, loss=loss, training_hooks=fisher_hook, train_op=train_op)


def meta(features, labels, mode, params):
    model = FullyConnectedNetwork()

    if mode == tf.estimator.ModeKeys.TRAIN:
        joint_features, base_features0, base_features1 = features
        joint_labels, base_labels0, base_labels1 = labels
        logits = model(joint_features)
        predictions = tf.argmax(logits, axis=1)
        one_hot_labels = tf.one_hot(joint_labels, 10)
        loss = tf.losses.softmax_cross_entropy(one_hot_labels, logits)

    if mode == tf.estimator.ModeKeys.EVAL:
        eval_logits = model(features)
        predictions = tf.argmax(eval_logits, axis=1)
        one_hot_labels = tf.one_hot(labels, 10)
        eval_loss = tf.losses.softmax_cross_entropy(one_hot_labels, eval_logits)
        accuracy = tf.metrics.accuracy(labels, predictions)
        return tf.estimator.EstimatorSpec(mode, loss=eval_loss, eval_metric_ops={'accuracy': accuracy})

    opt = tf.train.GradientDescentOptimizer(learning_rate=params['learning_rate'])

    grads_and_vars = opt.compute_gradients(loss)
    train_op = opt.apply_gradients(grads_and_vars, global_step=tf.train.get_global_step())

    grad, var = zip(*grads_and_vars)

    meta_model = MetaNetwork()
    meta_logits = meta_model(grads)

    features, labels
    features_joint, labels_joint

    logits = base(features)
    loss = loss_fn(logits, labels)

    base_grads_and_vars_all = optimizer.compute_gradients(loss)

    base_grads_and_vars = choose_fn(base_grads_and_vars, base.weights)

    base_train_op = optimizer.apply_gradients(base_grads_and_vars)

    logits_joint = base(features_joint)
    loss_joint = loss_fn(logits_joint, labels_joint)

    outputs = meta(base.weights, base_grads)
    loss_meta = meta_loss_fn(outputs, base_grads_joint)

    meta_grads_and_vars = choose_fn(meta_grads_and_vars, meta.weights)

    meta_train_op = optimizer_meta.apply(base)

    train_op = [base_train_op, meta_train_op]

    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)


class FullyConnectedNetwork(tf.keras.models.Model):
    def __init__(self):
        super(FullyConnectedNetwork, self).__init__()
        self.net = tf.keras.Sequential([
            tf.keras.layers.InputLayer((784,)),
            tf.keras.layers.Dense(100, activation='relu'),
            tf.keras.layers.Dense(100, activation='relu'),
            tf.keras.layers.Dense(10)])

    def call(self, inputs, training=None, mask=None):
        return self.net(inputs)


class GradientAccumulationHook(tf.train.SessionRunHook):
    def __init__(self, grad_and_var):
        print("Start Accumulation")
        self.gradients = grad_and_var[0]
        self.variable = grad_and_var[1]
        self.name = self.variable.name[:-2]

    def begin(self):
        self.sum_gradients = tf.Variable(tf.zeros_like(self.gradients), name=(self.name + '/fisher'))
        self.global_step = tf.train.get_global_step()
        self.sum_operation = self.sum_gradients.assign_add(tf.math.square(self.gradients))

    def before_run(self, run_context):
        return tf.train.SessionRunArgs({'gradient': self.sum_operation, 'global_step': self.global_step})

    def save_fisher_component(self, results):
        if results['global_step'] % 1000 == 0:
            print(self.name, ': ', np.linalg.norm(results['gradient']))

    def after_run(self, run_context, run_values):
        _ = run_context
        self.save_fisher_component(run_values.results)
