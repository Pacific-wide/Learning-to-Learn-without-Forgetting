import tensorflow as tf
import numpy as np

from dataset import dataset
from model import grouplearner
from optimizer import optimizer as op
from optimizer import spec
from optimizer import metric

from result import logger


def main(argv):
    seed = int(argv[1])
    alpha = float(argv[2])
    learning_rate = 5e-4
    n_epoch = 1
    n_batch = 100
    n_task = 10
    learning_rates = learning_rate * np.ones(n_task)
    learning_specs = []

    # model path
    model_dir = "meta_whole"
    np.random.seed(seed)

    # config
    run_config = tf.estimator.RunConfig(model_dir=model_dir, save_checkpoints_steps=60000/n_batch)
    ws0 = tf.estimator.WarmStartSettings(ckpt_to_initialize_from=model_dir, vars_to_warm_start=["meta"])
    ws1 = tf.estimator.WarmStartSettings(ckpt_to_initialize_from=model_dir, vars_to_warm_start=["main", "meta"])

    # generate sequence dataset
    set_of_datasets = dataset.SetOfRandPermMnist(n_task)
    d_in = set_of_datasets.list[0].d_in

    # learning specs
    for i in range(n_task):
        opt = op.SGDOptimizer().build(learning_rates[i])
        opt_spec = spec.OptimizerSpec(opt, d_in)
        learning_specs.append(spec.LearningSpec(n_epoch, n_batch, n_task, model_dir, opt_spec, alpha))

    my_grouplearner = grouplearner.GroupGradientMetaTestLearner(set_of_datasets, learning_specs, n_task, run_config, ws0, ws1)

    accuracy_matrix = my_grouplearner.train_and_evaluate()

    avg_acc = metric.AverageAccuracy(accuracy_matrix).compute()
    tot_acc = metric.TotalAccuracy(accuracy_matrix).compute()
    avg_forget = metric.AverageForgetting(accuracy_matrix).compute()
    tot_forget = metric.TotalForgetting(accuracy_matrix).compute()

    metric_list = [avg_acc, tot_acc, avg_forget, tot_forget]

    filepath = "3r_" + model_dir + ".txt"
    # filepath = "intro2.txt"
    logger.save(filepath, accuracy_matrix, metric_list, seed, learning_specs)


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)
    tf.app.run()
