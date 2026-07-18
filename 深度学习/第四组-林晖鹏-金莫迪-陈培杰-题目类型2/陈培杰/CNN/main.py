import os

import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd

from Train_Test import get_data, train_model, test_model, measure_performance
from utils_vis import (
	plot_individual_model_metrics,
	plot_comparison_metrics,
	plot_test_accuracy_bar,
	plot_performance_metrics,
)

from SimpleCNN import get_SimpleNet, get_CustomNet
from ResNet import get_ResNet1
from DenseNet import get_DenseNet
from MobileNet0 import get_MobileNet
from Res2Net import get_Res2Net


def run_comparison(epochs=50, batch_size=512, output_dir='comparison_results', model_dir='model'):
	device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
	print(f'Using {device}')
	os.makedirs(output_dir, exist_ok=True)
	os.makedirs(model_dir, exist_ok=True)

	train_loader, validate_loader, test_loader = get_data(batch_size=batch_size)

	names = ['SimpleNet', 'CustomNet', 'ResNet', 'DenseNet', 'MobileNet', 'Res2Net']
	models = {
		names[0]: get_SimpleNet,
		names[1]: get_CustomNet,
		names[2]: get_ResNet1,
		names[3]: get_DenseNet,
		names[4]: get_MobileNet,
		names[5]: get_Res2Net,
	}

	history_dict = {}
	test_accuracy_results = {}
	performance_data = {}

	for name in names:
		model = models[name]().to(device)

		print(f"--- 正在训练 {name} ---")

		optimizer = optim.Adam(model.parameters(), lr=0.001)
		criterion = nn.CrossEntropyLoss()

		print(f"正在计算 {name} 的性能指标...")
		perf_metrics = measure_performance(model, device=device)
		performance_data[name] = perf_metrics
		print(f"{name} 性能: {perf_metrics}")

		train_losses, validate_losses, validate_accuracy = train_model(
			model, train_loader, validate_loader, criterion, optimizer, device, epochs=epochs
		)
		test_accuracy = test_model(model, test_loader, device)

		history_dict[name] = {
			'train_losses': train_losses,
			'validate_losses': validate_losses,
			'validate_accuracy': validate_accuracy
		}
		test_accuracy_results[name] = test_accuracy

		model_path = f'{model_dir}/{name}.pth'
		torch.save(model.state_dict(), model_path)
		print(f"模型已保存至: {model_path}")

		plot_individual_model_metrics(name, train_losses, validate_losses, validate_accuracy, output_dir)

	test_acc_df = pd.DataFrame(list(test_accuracy_results.items()), columns=['Model', 'Test_Accuracy'])
	test_acc_df.to_csv(f'{output_dir}/test_accuracy_results.csv', index=False)

	perf_df = pd.DataFrame.from_dict(performance_data, orient='index')
	perf_df.to_csv(f'{output_dir}/performance_data.csv', index_label='Model')

	print(f"\n--- 所有CSV数据已保存至 {output_dir} 目录 ---")

	plot_comparison_metrics(history_dict, output_dir)
	plot_test_accuracy_bar(test_accuracy_results, output_dir)
	plot_performance_metrics(performance_data, output_dir)


if __name__ == '__main__':
	run_comparison()
