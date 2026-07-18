from stu_upload.mnist_mlp_demo import MNIST_MLP, HIDDEN_DIMS, OUT
import test_cpu
import time
import numpy as np
import os
import sys



def evaluate(mlp):
    pred_results = np.zeros([mlp.test_data.shape[0]])
    
    for idx in range(mlp.test_data.shape[0]//mlp.batch_size):
        # print("batch %d"%idx)
        batch_images = mlp.test_data[idx*mlp.batch_size:(idx+1)*mlp.batch_size, :-1]
        data = batch_images.flatten().tolist()


        mlp.net.setInputData(data)


        start = time.time()
        mlp.forward()
        end = time.time()
        print('inferencing time: %f'%(end - start))
        prob = mlp.net.getOutputData()
        
       

        prob = np.array(prob).reshape((mlp.batch_size, mlp.out_classes))
        #print(prob)

        np.savetxt("result1.txt",prob);
        pred_labels = np.argmax(prob, axis=1)
        pred_results[idx*mlp.batch_size:(idx+1)*mlp.batch_size] = pred_labels
    
    if mlp.test_data.shape[0] % mlp.batch_size >0: 
        last_batch = mlp.test_data.shape[0]//mlp.batch_size*mlp.batch_size
        batch_images = mlp.test_data[-last_batch:, :-1]
        data = batch_images.flatten().tolist()
        mlp.net.setInputData(data)
        mlp.forward()
        prob = mlp.net.getOutputData()
        pred_labels = np.argmax(prob, axis=1)
        pred_results[-last_batch:] = pred_labels
    accuracy = np.mean(pred_results == mlp.test_data[:,-1])
    print('Accuracy in test set: %f' % accuracy)

def run_mnist():
    batch_size = 10000
    model_path = 'stu_upload/weight.npy'
    hidden_dims, c = HIDDEN_DIMS, OUT
    if os.path.exists(model_path):
        params = np.load(model_path, allow_pickle=True, encoding="latin1").item()
        layer_count = len([key for key in params.keys() if key.startswith('w')])
        hidden_dims = [int(params['w%d' % idx].shape[1]) for idx in range(1, layer_count)]
        c = int(params['w%d' % layer_count].shape[1])
    mlp = MNIST_MLP()
   
    mlp.build_model(batch_size=batch_size, hidden_dims=hidden_dims, out_classes=c)
    
    test_data = '../mnist_data/t10k-images-idx3-ubyte'
    test_label = '../mnist_data/t10k-labels-idx1-ubyte'
    mlp.load_data(test_data, test_label)
    mlp.load_model(model_path)

    for i in range(10):
        evaluate(mlp)

if __name__ == '__main__':
    print('-------- TEST CPU --------')
    test_cpu.run_test()
    print('-------- TEST DLP --------')
    run_mnist()
