import sys
import numpy as np
import struct
import os
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from layers_1 import FullyConnectedLayer, ReLULayer, SoftmaxLossLayer

MNIST_DIR = "../mnist_data"
TRAIN_DATA = "train-images-idx3-ubyte"
TRAIN_LABEL = "train-labels-idx1-ubyte"
TEST_DATA = "t10k-images-idx3-ubyte"
TEST_LABEL = "t10k-labels-idx1-ubyte"


def show_matrix(mat, name):
    #print(name + str(mat.shape) + ' mean %f, std %f' % (mat.mean(), mat.std()))
    pass


class MNIST_MLP(object):
    def __init__(self, batch_size=100, input_size=784, hidden_dims=None, out_classes=10, lr=0.1, max_epoch=1, print_iter=100):
        self.batch_size = batch_size
        self.input_size = input_size
        if hidden_dims is None:
            hidden_dims = [256, 128, 64, 32]
        self.hidden_dims = hidden_dims
        self.out_classes = out_classes
        self.lr = lr
        self.max_epoch = max_epoch
        self.print_iter = print_iter

    # 上传数据集
    def load_mnist(self, file_dir, is_images=True):
        bin_file = open(file_dir, 'rb')
        bin_data = bin_file.read()
        bin_file.close()


        if is_images:
           fmt_header = '>iiii'
           magic,num_images,num_rows,num_cols=struct.unpack_from(fmt_header,bin_data,0)
        else:
           fmt_header = '>ii'
           magic,num_images=struct.unpack_from(fmt_header,bin_data,0)
           num_rows, num_cols= 1,1
        data_size = num_images * num_rows * num_cols
        mat_data = struct.unpack_from('>' + str(data_size) + 'B', bin_data, struct.calcsize(fmt_header))

        mat_data = np.reshape(mat_data,[num_images,num_rows*num_cols])
        print('Load images from %s, number: %d, data shape: %s' % (file_dir, num_images, str(mat_data.shape)))
        return mat_data

    def load_data(self):
        # TODO: 调用函数 load_mnist 读取和预处理 MNIST 中训练数据和测试数据的图像和标记
        print('Loading MNIST data from files...')
        train_images = self.load_mnist(os.path.join(MNIST_DIR, TRAIN_DATA), True).astype(np.float32) / 255.0
        train_labels = self.load_mnist(os.path.join(MNIST_DIR, TRAIN_LABEL), False)
        test_images = self.load_mnist(os.path.join(MNIST_DIR, TEST_DATA), True).astype(np.float32) / 255.0
        test_labels = self.load_mnist(os.path.join(MNIST_DIR, TEST_LABEL), False)
        
        self.train_data=np.append(train_images,train_labels, axis=1)
        self.test_data=np.append(test_images, test_labels, axis=1)


    # 打乱数据
    def shuffle_data(self):
        print('Randomly shuffle MNIST data...')
        np.random.shuffle(self.train_data)

    def build_model(self):  # 建立网络结构
        # TODO：建立五层全连接神经网络结构
        print('Building multi-layer perception model...')
        self.fc_layers = []
        self.relu_layers = []
        layer_dims = [self.input_size] + self.hidden_dims + [self.out_classes]

        for idx in range(len(layer_dims) - 1):
            fc_layer = FullyConnectedLayer(layer_dims[idx], layer_dims[idx + 1])
            self.fc_layers.append(fc_layer)
            setattr(self, 'fc%d' % (idx + 1), fc_layer)
            if idx < len(layer_dims) - 2:
                relu_layer = ReLULayer()
                self.relu_layers.append(relu_layer)
                setattr(self, 'relu%d' % (idx + 1), relu_layer)

        self.softmax = SoftmaxLossLayer()
        self.update_layer_list = self.fc_layers

    def init_model(self):
        print('Initializing parameters of each layer in MLP...')
        for layer in self.update_layer_list:
            layer.init_param()
    def load_model(self, param_dir):
        print('Loading parameters from file ' + param_dir)
        params = np.load(param_dir, allow_pickle=True).item()
        for idx, layer in enumerate(self.fc_layers, start=1):
            layer.load_param(params['w%d' % idx], params['b%d' % idx])


    def save_model(self, param_dir):
        print('Saving parameters to file ' + param_dir)
        params = {}
        for idx, layer in enumerate(self.fc_layers, start=1):
            params['w%d' % idx], params['b%d' % idx] = layer.save_param()
        print( params)
        np.save(param_dir, np.array(params, dtype=object), allow_pickle=True)


    def forward(self, input):  # 神经网络的前向传播
        # TODO：神经网络的前向传播
        output = input
        for idx, fc_layer in enumerate(self.fc_layers):
            output = fc_layer.forward(output)
            if idx < len(self.relu_layers):
                output = self.relu_layers[idx].forward(output)
        prob = self.softmax.forward(output)
        return prob



    def backward(self):   # 神经网络的反向传播
        # TODO：神经网络的反向传播
        dloss = self.softmax.backward()
        grad = dloss
        for idx in range(len(self.fc_layers) - 1, -1, -1):
            grad = self.fc_layers[idx].backward(grad)
            if idx > 0:
                grad = self.relu_layers[idx - 1].backward(grad)

    def update(self,lr):
        for layer in self.update_layer_list:
            layer.update_param(lr)
    



    def train(self):
        max_batch=self.train_data.shape[0] // self.batch_size ###python3

        print('Start training...')
        for idx_epoch in range(self.max_epoch):
            self.shuffle_data()
            for idx_batch in range(max_batch):
                batch_images = self.train_data[idx_batch*self.batch_size:(idx_batch+1)*self.batch_size,:-1] ##batchsize ,最后1列
                batch_labels = self.train_data[idx_batch*self.batch_size:(idx_batch+1)*self.batch_size,-1]
                prob = self.forward(batch_images)
                loss = self.softmax.get_loss(batch_labels)
                self.backward()
                self.update(self.lr)
                if idx_batch % self.print_iter == 0:
                   print('Epoch %d, iter %d, loss: %.6f' % (idx_epoch, idx_batch, loss))
       



    def evaluate(self):
        pred_results = np.zeros([self.test_data.shape[0]])
        for idx in range(int(self.test_data.shape[0]/self.batch_size)):
            batch_images=self.test_data[idx*self.batch_size:(idx+1)*self.batch_size, :-1]
            prob = self.forward(batch_images)
            pred_labels=np.argmax(prob,axis=1)
            pred_results[idx*self.batch_size:(idx+1)*self.batch_size]=pred_labels
        accuracy = np.mean(pred_results==self.test_data[:,-1])
        print('Accuracy in test  set:%f' % accuracy)


def build_mnist_mlp(param_dir='weight.npy'):
    params = np.load(param_dir, allow_pickle=True).item()
    input_size = int(params['w1'].shape[0])
    layer_count = len([key for key in params.keys() if key.startswith('w')])
    hidden_dims = [int(params['w%d' % idx].shape[1]) for idx in range(1, layer_count)]
    out_classes = int(params['w%d' % layer_count].shape[1])
    e = 10
    mlp = MNIST_MLP(
        batch_size=10000,
        input_size=input_size,
        hidden_dims=hidden_dims,
        out_classes=out_classes,
        max_epoch=e,
    )
    mlp.load_data()
    mlp.build_model()
    mlp.init_model()
    # mlp.train()
    # mlp.save_model('mlp-%s-%depoch.npy' % ('-'.join(map(str, hidden_dims)), e))
    mlp.load_model(param_dir)
    return mlp


if __name__ == '__main__':
    mlp = build_mnist_mlp()
    mlp.evaluate()
