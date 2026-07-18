import numpy as np
import struct
import os
import time
from numpy.lib.stride_tricks import as_strided

def show_matrix(mat, name):
    #print(name + str(mat.shape) + ' mean %f, std %f' % (mat.mean(), mat.std()))
    pass

def show_time(time, name):
    #print(name + str(time))
    pass


def im2col(input_data, kernel_size, stride):
    N, C, H, W = input_data.shape
    KH, KW = kernel_size, kernel_size
    H_out = (H - KH)//stride + 1
    W_out = (W - KW)//stride + 1

    cols = np.zeros((N, C, KH, KW, H_out, W_out))
    for y in range(KH):
        y_max = y + stride*H_out
        for x in range(KW):
            x_max = x + stride*W_out
            cols[:, :, y, x, :, :] = input_data[:, :, y:y_max:stride, x:x_max:stride]

    cols = cols.transpose(0, 4, 5, 1, 2, 3).reshape(N*H_out*W_out, -1)
    return cols

class ConvolutionalLayer(object):
    def __init__(self, kernel_size, channel_in, channel_out, padding, stride):
        # 卷积层的初始化
        self.kernel_size = kernel_size
        self.channel_in = channel_in
        self.channel_out = channel_out
        self.padding = padding
        self.stride = stride
        print('\tConvolutional layer with kernel size %d, input channel %d, output channel %d.' % (self.kernel_size, self.channel_in, self.channel_out))
    import numpy as np

    
    def init_param(self, std=0.01):  # 参数初始化
        self.weight = np.random.normal(loc=0.0, scale=std, size=(self.channel_in, self.kernel_size, self.kernel_size, self.channel_out))
        self.bias = np.zeros([self.channel_out])

    def forward(self, input):
        self.input = input
        N, C, H, W = input.shape

        # padding
        H_pad, W_pad = H + 2*self.padding, W + 2*self.padding
        input_pad = np.zeros((N, C, H_pad, W_pad))
        input_pad[:, :, self.padding:H+self.padding, self.padding:W+self.padding] = input

        # 输出尺寸
        H_out = (H_pad - self.kernel_size)//self.stride + 1
        W_out = (W_pad - self.kernel_size)//self.stride + 1

        # im2col
        X_col = im2col(input_pad, self.kernel_size, self.stride)  # (N*H_out*W_out, C*K*K)

        # weight reshape
        W_col = self.weight.reshape(-1, self.channel_out)          # (C*K*K, C_out)

        # 矩阵乘法
        out = X_col @ W_col + self.bias                             # (N*H_out*W_out, C_out)
        out = out.reshape(N, H_out, W_out, self.channel_out).transpose(0,3,1,2)  # (N, C_out, H_out, W_out)

        self.output = out
        return self.output

    def load_param(self, weight, bias):  # 参数加载
        # print('Loading parameter for layer: ' + self.__class__.__name__)
        # print('Weight shape: ' + str(weight.shape))
        # print('Bias shape: ' + str(bias.shape))
        # print(self.weight.shape)
        # print(self.bias.shape)
        assert self.weight.shape == weight.shape
        assert self.bias.shape == bias.shape
        self.weight = weight
        self.bias = bias

class MaxPoolingLayer(object):
    def __init__(self, kernel_size, stride): # 最大池化层的初始化
        self.kernel_size = kernel_size
        self.stride = stride
        print('\tMax pooling layer with kernel size %d, stride %d.' % (self.kernel_size, self.stride))
    def forward(self, input):
        self.input = input  # [N, C, H, W]
        N, C, H, W = input.shape

        x = input

        H_out = (H - self.kernel_size)//self.stride + 1
        W_out = (W - self.kernel_size)//self.stride + 1

        shape = (N, C, H_out, W_out, self.kernel_size, self.kernel_size)
        strides = (
            x.strides[0],
            x.strides[1],
            self.stride * x.strides[2],
            self.stride * x.strides[3],
            x.strides[2],
            x.strides[3]
        )

        windows = as_strided(x, shape=shape, strides=strides)
        out = windows.max(axis=(4,5))

        self.output = out
        return self.output

class FlattenLayer(object):
    def __init__(self, input_shape, output_shape):  # 扁平化层的初始化
        self.input_shape = input_shape
        self.output_shape = output_shape
        assert np.prod(self.input_shape) == np.prod(self.output_shape)
        print('\tFlatten layer with input shape %s, output shape %s.' % (str(self.input_shape), str(self.output_shape)))
    def forward(self, input):   # 前向传播的计算
        assert list(input.shape[1:]) == list(self.input_shape)
        # matconvnet feature map dim: [N, height, width, channel]
        # ours feature map dim: [N, channel, height, width]
        self.input = input.transpose([0, 2, 3, 1])
        self.output = self.input.reshape([self.input.shape[0]] + list(self.output_shape))
        show_matrix(self.output, 'flatten out ')
        return self.output
