import time

import torch
from torch.utils.data import DataLoader, random_split
import torchvision.transforms as T
import torchvision.datasets as datasets
from thop import profile


def get_data(batch_size=128, data_dir="data"):
	transform = T.Compose([
		T.ToTensor(),
		T.Normalize(mean=(0.4914, 0.4822, 0.4465), std=(0.2023, 0.1994, 0.2010))
	])
	train_dataset = datasets.CIFAR10(data_dir, train=True, transform=transform, download=True)
	test_dataset = datasets.CIFAR10(data_dir, train=False, transform=transform, download=True)
	train_dataset, validate_dataset = random_split(train_dataset, [0.9, 0.1])

	train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
	validate_loader = DataLoader(validate_dataset, batch_size=batch_size, shuffle=False)
	test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

	return train_loader, validate_loader, test_loader


def train_model(model, train_loader, validate_loader, criterion, optimizer, device, epochs=40):
	train_losses = []
	validate_losses = []
	validate_accuracy = []

	for epoch in range(epochs):
		model.train()
		train_loss = 0
		for x, y in train_loader:
			x, y = x.to(device), y.to(device)
			y_output = model(x)

			loss = criterion(y_output, y)
			optimizer.zero_grad()
			loss.backward()
			optimizer.step()

			train_loss += loss.item()

		train_loss /= len(train_loader)
		train_losses.append(train_loss)

		model.eval()
		validate_loss = 0
		corrects = 0
		with torch.no_grad():
			for x, y in validate_loader:
				x, y = x.to(device), y.to(device)
				y_output = model(x)

				loss = criterion(y_output, y)
				validate_loss += loss.item()

				y_pred = torch.argmax(y_output, dim=1)
				corrects += (y_pred == y).sum().item()
			accuracy = corrects / len(validate_loader.dataset)

		validate_losses.append(validate_loss)
		validate_accuracy.append(accuracy)

		print(f"Epoch: [{epoch + 1}/{epochs}], Train_loss = {train_loss} | Validate_loss = {validate_loss} | Accuracy = {accuracy}")

	return train_losses, validate_losses, validate_accuracy


def test_model(model, test_loader, device):
	model.eval()
	accuracy = 0
	with torch.no_grad():
		for x, y in test_loader:
			x, y = x.to(device), y.to(device)
			y_output = model(x)
			y_pred = torch.argmax(y_output, dim=1)
			accuracy += (y_pred == y).sum().item()
	return accuracy / len(test_loader.dataset)


def measure_performance(model, input_size=None, device=torch.device('cuda')):
	"""
	计算模型的 Params(M), FLOPs(G), Latency(ms), Peak Memory(MB)
	"""
	if input_size is None:
		input_size = [1, 3, 32, 32]

	model.eval()
	dummy_input = torch.randn(input_size).to(device)

	total_params = sum(p.numel() for p in model.parameters())
	params_m = total_params / 1e6

	macs, _ = profile(model, inputs=(dummy_input,), verbose=False)
	flops_g = macs * 2 / 1e9

	with torch.no_grad():
		for _ in range(20):
			_ = model(dummy_input)
	iterations = 100
	if device.type == 'cuda':
		start_event = [torch.cuda.Event(enable_timing=True) for _ in range(iterations)]
		end_event = [torch.cuda.Event(enable_timing=True) for _ in range(iterations)]

		with torch.no_grad():
			for i in range(iterations):
				start_event[i].record()
				_ = model(dummy_input)
				end_event[i].record()

		torch.cuda.synchronize()
		times = [s.elapsed_time(e) for s, e in zip(start_event, end_event)]
		latency_ms = sum(times) / iterations
	else:
		start_time = time.time()
		with torch.no_grad():
			for _ in range(iterations):
				_ = model(dummy_input)
		latency_ms = (time.time() - start_time) / iterations * 1000

	peak_mem_mb = 0
	if device.type == 'cuda':
		torch.cuda.reset_peak_memory_stats(device)
		with torch.no_grad():
			_ = model(dummy_input)
		peak_mem_mb = torch.cuda.max_memory_allocated(device)
		peak_mem_mb /= 1024 ** 2

	return {
		'params': params_m,
		'flops': flops_g,
		'latency': latency_ms,
		'peak_mem': peak_mem_mb
	}
