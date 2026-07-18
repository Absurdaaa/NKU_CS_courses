import sys
import numpy as np
import struct
import os
import time

def show_matrix(mat, name):
    #print(name + str(mat.shape) + ' mean %f, std %f' % (mat.mean(), mat.std()))
    pass

def show_time(time, name):
    #print(name + str(time))
    pass


class FullyConnectedLayer(object):
    def __init__(self, num_input, num_output):
        self.num_input = num_input
        self.num_output = num_output
        print('\tFully connected layer with input %d, output %d.' % (self.num_input, self.num_output))

    def init_param(self, std=0.01):
        self.weight = np.random.normal(0.0, std, (self.num_input, self.num_output))
        self.bias = np.zeros([1, self.num_output])
        show_matrix(self.weight, 'fc weight ')
        show_matrix(self.bias, 'fc bias ')

    def forward(self, input):
        self.input = input
        batch_size = input.shape[0]
        self.output = np.zeros((batch_size, self.num_output))
        for i in range(batch_size):
            # 内层循环替换为向量运算
            self.output[i, :] = input[i, :] @ self.weight + self.bias[0, :]
        return self.output

    def backward(self, top_diff):
        batch_size = top_diff.shape[0]
        self.d_weight = np.zeros_like(self.weight)
        self.d_bias = np.zeros_like(self.bias)
        bottom_diff = np.zeros((batch_size, self.num_input))
        # 用for循环计算梯度
        for i in range(batch_size):
            for j in range(self.num_output):
                self.d_bias[0, j] += top_diff[i, j]
                for k in range(self.num_input):
                    self.d_weight[k, j] += self.input[i, k] * top_diff[i, j]
                    bottom_diff[i, k] += self.weight[k, j] * top_diff[i, j]
        return bottom_diff

    def get_gradient(self):
        return self.d_weight, self.d_bias

    def update_param(self, lr):
        d_weight, d_bias = self.get_gradient()
        self.weight -= lr * d_weight
        self.bias -= lr * d_bias

    def load_param(self, weight, bias):
        assert self.weight.shape == weight.shape
        assert self.bias.shape == bias.shape
        self.weight = weight
        self.bias = bias
        show_matrix(self.weight, 'fc weight ')
        show_matrix(self.bias, 'fc bias ')

    def save_param(self):
        show_matrix(self.weight, 'fc weight ')
        show_matrix(self.bias, 'fc bias ')
        return self.weight, self.bias


class ReLULayer(object):
    def __init__(self):
        print('\tRelu layer')

    def forward(self, input):
        self.input = input
        batch_size, dim = input.shape
        output = np.zeros_like(input)
        for i in range(batch_size):
            for j in range(dim):
                output[i, j] = input[i, j] if input[i, j] > 0 else 0.0
        return output

    def backward(self, top_diff):
        batch_size, dim = top_diff.shape
        bottom_diff = np.zeros_like(top_diff)
        for i in range(batch_size):
            for j in range(dim):
                bottom_diff[i, j] = top_diff[i, j] if self.input[i, j] > 0 else 0.0
        return bottom_diff


class SoftmaxLossLayer(object):
    def __init__(self):
        print('\tSoftmax loss layer.')

    def forward(self, input):
        batch_size, num_class = input.shape
        self.prob = np.zeros_like(input)
        for i in range(batch_size):
            row_max = np.max(input[i])
            exp_sum = 0.0
            for j in range(num_class):
                self.prob[i, j] = np.exp(input[i, j] - row_max)
                exp_sum += self.prob[i, j]
            for j in range(num_class):
                self.prob[i, j] /= exp_sum
        return self.prob

    def get_loss(self, label):
        batch_size, num_class = self.prob.shape
        self.label_onehot = np.zeros_like(self.prob)
        for i in range(batch_size):
            self.label_onehot[i, label[i]] = 1.0
        loss = 0.0
        for i in range(batch_size):
            for j in range(num_class):
                if self.label_onehot[i, j] > 0:
                    loss -= np.log(self.prob[i, j])
        loss /= batch_size
        return loss

    def backward(self):
        batch_size, num_class = self.prob.shape
        bottom_diff = np.zeros_like(self.prob)
        for i in range(batch_size):
            for j in range(num_class):
                bottom_diff[i, j] = (self.prob[i, j] - self.label_onehot[i, j]) / batch_size
        return bottom_diff