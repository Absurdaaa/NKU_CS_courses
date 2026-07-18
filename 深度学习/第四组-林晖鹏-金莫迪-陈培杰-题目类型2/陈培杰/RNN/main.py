import os

import torch
import torch.nn as nn
import torch.optim as optim

from NameDataset import NameDataset, n_letters, get_train_test_data, get_dataloader
from TrainAndTest import train_model, evaluate_model, train_and_validate_model
from Plot import plot_learning_curves, plot_confusion_matrices, save_metrics_to_txt, save_test_accuracy_to_csv
from RNN import CharRNN
from LSTM import CharLSTM
from GRU import CharGRU

def get_rnn(input_size, hidden_size, output_size, num_layers, device):
    return CharRNN(input_size, hidden_size, output_size, num_layers).to(device)

def get_lstm(input_size, hidden_size, output_size, num_layers, device):
    return CharLSTM(input_size, hidden_size, output_size, num_layers).to(device)

def get_gru(input_size, hidden_size, output_size, num_layers, device):
    return CharGRU(input_size, hidden_size, output_size, num_layers).to(device)

def main():
    epochs = 150

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Using {device}')

    os.makedirs('results', exist_ok=True)

    all_data = NameDataset('data/names')
    train_dataset, test_dataset = get_train_test_data(all_data)
    train_small_dataset, validate_dataset = get_train_test_data(train_dataset)

    train_loader = get_dataloader(train_dataset)
    train_small_loader = get_dataloader(train_small_dataset)
    validate_loader = get_dataloader(validate_dataset)
    test_loader = get_dataloader(test_dataset)

    rnn1_config = [n_letters, 128, len(all_data.labels_uniq), 1, get_rnn]
    rnn2_config = [n_letters, 128, len(all_data.labels_uniq), 2, get_rnn]
    lstm1_config = [n_letters, 128, len(all_data.labels_uniq), 1, get_lstm]
    lstm2_config = [n_letters, 128, len(all_data.labels_uniq), 2, get_lstm]
    gru1_config = [n_letters, 128, len(all_data.labels_uniq), 1, get_gru]
    gru2_config = [n_letters, 128, len(all_data.labels_uniq), 2, get_gru]


    models_config = {
        'RNN_1': rnn1_config,
        'RNN_2': rnn2_config,
        'LSTM_1': lstm1_config,
        'LSTM_2': lstm2_config,
        'GRU_1': gru1_config,
        'GRU_2': gru2_config
    }

    all_results = {}

    for model_name, config in models_config.items():
        print(f"========== 开始训练 {model_name} ==========")
        input_size, hidden_size, output_size, num_layers, func = config
        criterion = nn.CrossEntropyLoss()

        print("-> 阶段1：验证集性能评估与绘制曲线")

        model_eval = func(input_size, hidden_size, output_size, num_layers, device)
        optimizer_eval = optim.Adam(model_eval.parameters(), lr=0.01)
        train_losses, validate_losses, validate_accuracy = train_and_validate_model(model=model_eval, train_loader=train_small_loader,
                                                                                    validate_loader=validate_loader,
                                                                                    optimizer=optimizer_eval, criterion=criterion,
                                                                                    device=device, epochs=epochs)

        print("-> 阶段2：训练集全训练")
        best_epoch = max(120, validate_losses.index(min(validate_losses)) + 1)
        print(f"[{model_name}] 选择 Epoch: {best_epoch}")

        model = func(input_size, hidden_size, output_size, num_layers, device)
        optimizer = optim.Adam(model.parameters(), lr=0.01)

        train_model(model=model, train_loader=train_loader, optimizer=optimizer, criterion=criterion, device=device, epochs=best_epoch)

        # 在测试集上评估获取预测结果
        print("-> 阶段3：测试集独立评估")
        y_true, y_pred, test_acc = evaluate_model(model=model, test_loader=test_loader, device=device)

        # 将结果打包存入字典
        all_results[model_name] = {
            'train_losses': train_losses,
            'validate_losses': validate_losses,
            'validate_accuracy': validate_accuracy,
            'y_true': y_true,
            'y_pred': y_pred
        }

    my_classes = all_data.labels_uniq

    plot_learning_curves(all_results)
    plot_confusion_matrices(all_results, class_names=my_classes)
    save_metrics_to_txt(all_results, filename="results/evaluation_results.txt", class_names=my_classes)
    save_test_accuracy_to_csv(all_results, filename="results/test_accuracy.csv")


if __name__ == '__main__':
    main()
