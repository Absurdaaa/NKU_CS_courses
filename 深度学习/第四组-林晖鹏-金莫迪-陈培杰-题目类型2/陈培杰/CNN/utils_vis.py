import matplotlib.pyplot as plt


plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def _get_colors(count):
	base_colors = list(plt.cm.tab10.colors)
	if count <= len(base_colors):
		return base_colors[:count]
	cmap = plt.cm.get_cmap('tab20', count)
	return [cmap(i) for i in range(count)]


def plot_individual_model_metrics(name, train_losses, validate_losses, validate_accuracy, output_dir):
	epochs = range(1, len(train_losses) + 1)
	fig, ax1 = plt.subplots(figsize=(8, 5))

	ax1.set_xlabel('迭代轮次 (Epochs)')
	ax1.set_ylabel('损失值 (Loss)', color='tab:red')
	ax1.plot(epochs, train_losses, label='训练集损失', color='tab:red', linestyle='-')
	ax1.plot(epochs, validate_losses, label='验证集损失', color='tab:orange', linestyle='--')
	ax1.tick_params(axis='y', labelcolor='tab:red')

	ax2 = ax1.twinx()
	ax2.set_ylabel('准确率 (Accuracy)', color='tab:blue')
	ax2.plot(epochs, validate_accuracy, label='验证集准确率', color='tab:blue', linestyle='-')
	ax2.tick_params(axis='y', labelcolor='tab:blue')

	plt.title(f'{name} 训练指标图')
	fig.legend(loc='upper right', bbox_to_anchor=(1, 1), bbox_transform=ax1.transAxes)
	plt.tight_layout()

	plt.savefig(f'{output_dir}/{name}_metrics.png')
	plt.close()


def plot_comparison_metrics(history_dict, output_dir):
	fig, axes = plt.subplots(1, 3, figsize=(18, 5))

	for name, metrics in history_dict.items():
		epochs = range(1, len(metrics['train_losses']) + 1)
		axes[0].plot(epochs, metrics['train_losses'], label=name)
		axes[1].plot(epochs, metrics['validate_losses'], label=name)
		axes[2].plot(epochs, metrics['validate_accuracy'], label=name)

	axes[0].set_title('训练集损失对比')
	axes[1].set_title('验证集损失对比')
	axes[2].set_title('验证集准确率对比')

	for ax in axes:
		ax.legend()
		ax.grid(True)

	plt.tight_layout()
	plt.savefig(f'{output_dir}/model_comparison_lines.png')
	plt.close()


def plot_test_accuracy_bar(test_accuracy_results, output_dir):
	names = list(test_accuracy_results.keys())
	accuracies = list(test_accuracy_results.values())
	colors = _get_colors(len(names))

	plt.figure(figsize=(8, 5))
	bars = plt.bar(names, accuracies, color=colors)

	for bar in bars:
		yval = bar.get_height()
		plt.text(bar.get_x() + bar.get_width() / 2, yval + 0.005, f'{yval:.4f}', ha='center', va='bottom')

	plt.title('各模型测试集准确率对比')
	plt.ylabel('准确率')
	plt.tight_layout()
	plt.savefig(f'{output_dir}/test_accuracy_bar.png')
	plt.close()


def plot_performance_metrics(performance_results, output_dir):
	names = list(performance_results.keys())
	metrics = ['params', 'flops', 'latency', 'peak_mem']
	titles = ['参数量 (M)', '计算量 (GFLOPs)', '推理延迟 (ms)', '显存峰值 (MB)']
	colors = _get_colors(len(names))

	fig, axes = plt.subplots(2, 2, figsize=(12, 10))
	axes = axes.flatten()

	for i, metric in enumerate(metrics):
		values = [performance_results[name][metric] for name in names]
		axes[i].bar(names, values, color=colors)
		axes[i].set_title(titles[i])

	plt.tight_layout()
	plt.savefig(f'{output_dir}/performance_metrics.png')
	plt.close()
