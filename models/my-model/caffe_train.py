__author__ = 'shengjia'

import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')

if len(sys.argv) > 1:
    solver_file = sys.argv[1]
    print("Solver file: " + str(solver_file))
else:
    print("Usage: caffe_train.py solver_file")
    exit(-1)

# The caffe module needs to be on the Python path;
#  we'll add it here explicitly.
caffe_root = '/home/ubuntu/caffe/'  # this file should be run from {caffe_root}/examples (otherwise change this line)
sys.path.insert(0, caffe_root + 'python')
import caffe
caffe.set_device(0)
caffe.set_mode_gpu()

pretrained_model = caffe_root + 'models/bvlc_reference_caffenet/bvlc_reference_caffenet.caffemodel'

import os
os.chdir('/home/ubuntu/deep-visualization-toolbox/models/my-model')

### load the solver and create train and test nets
solver = None  # ignore this workaround for lmdb data (can't instantiate two solvers on the same data)
solver = caffe.SGDSolver(solver_file)
solver.net.copy_from(pretrained_model)

transformer = caffe.io.Transformer({'data': solver.net.blobs['data'].data.shape})
data_mean = np.load('ilsvrc12/ilsvrc_2012_mean.npy').mean(1).mean(1)
transformer.set_transpose('data', (2,0,1))
transformer.set_mean('data', data_mean - 8)  # Subtract a bit more to avoid overflow, only for visualization
transformer.set_channel_swap('data', (2,1,0))
transformer.set_raw_scale('data', 255.0)

lookup_file = 'ilsvrc12/synset_words.txt'
lines = open(lookup_file).readlines()
names = [line.split()[1] for line in lines]

import time
niter = 20000
test_interval = 100
save_interval = 10000
# losses will also be stored in the log
train_loss = np.zeros(niter)
test_acc = np.zeros(int(np.ceil(niter / test_interval)))
output = np.zeros((niter, 8, 10))

begin_time = time.time()

if not os.path.isdir('output'):
    os.mkdir('output')
logger = open('output/log', 'w')
test_logger = open('output/test_log', 'w')

sparse_layers = ['conv3', 'conv4', 'conv5']

# the main solver loop
for it in range(niter):
    step_time = time.time()
    solver.step(1)  # SGD by Caffe
    elapsed_time = time.time() - step_time

    # store the train loss
    train_loss[it] = solver.net.blobs['loss'].data
    print("Iter " + str(it) + " -- Train loss: " + str(train_loss[it]) +
          " -- Time used: " + str(elapsed_time) + "s -- Total time: " + str(time.time() - begin_time) + "s")
    logger.write(str(it) + " " + str(train_loss[it]) + " " + str(elapsed_time) + "\n")

    # Compute average activations once in a while
    if it % test_interval == 0:
        test_logger.write("Average activation: ")
        for sparse_layer in sparse_layers:
            activation = np.average(solver.net.blobs[sparse_layer].data)
            print(str(activation) + "(" + sparse_layer + ")"),
            test_logger.write(str(activation) + "(" + sparse_layer + ") ")
        print("")
        test_logger.write("\n")

    # run a full test every so often
    # (Caffe can also do this for us and write to a log, but we show here
    #  how to do it directly in Python, where more complicated things are easier.)
    if it % test_interval == 0:
        print 'Iteration', it, 'testing...'
        correct = 0
        batch_size = solver.test_nets[0].blobs['data'].data.shape[0]
        for test_it in range(100):
            solver.test_nets[0].forward()
            correct += sum(solver.test_nets[0].blobs['fc8'].data.argmax(1)
                           == solver.test_nets[0].blobs['label'].data)
        test_acc[it // test_interval] = correct / 100.0 / batch_size
        print("Test accuracy: " + str(correct / 100.0 / batch_size))
        test_logger.write("Test accuracy@iter " + str(it) + " " + str(correct / 100.0 / batch_size) + "\n")
        test_logger.flush()
        logger.flush()

    if it % save_interval == 0:
        print("Saving net")
        solver.net.save('output/' + solver_file.split('.')[0] + '.caffemodel')

logger.close()
test_logger.close()
