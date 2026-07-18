import glob
import math
import os
import random
import string
import time
import unicodedata

import torch
import torch.nn as nn

ALL_LETTERS = string.ascii_letters + " .,;'-"
N_LETTERS = len(ALL_LETTERS) + 1
def _ensure_batch_target(label_tensor):
    if label_tensor.dim() == 0:
        return label_tensor.unsqueeze(0)
    return label_tensor

def train_model(model, train_loader, optimizer, criterion, device, epochs=50):
    train_losses = []
    model.train()

    for epoch in range(epochs):
        train_loss = 0
        for batch in train_loader:
            label_tensors, data_tensors, lengths, data_labels, data_items = batch
            label_tensors, data_tensors = label_tensors.to(device), data_tensors.to(device)

            y_pred = model(data_tensors, lengths)

            loss = criterion(y_pred, label_tensors)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_loader)
        print(f"Epoch:[{epoch + 1}/{epochs}], Train_loss = {train_loss: .4f}")
        train_losses.append(train_loss)

def train_and_validate_model(model, train_loader, validate_loader, optimizer, criterion, device, epochs=50):
    train_losses = []
    validate_losses = []
    validate_accuracy = []

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for batch in train_loader:
            label_tensors, data_tensors, lengths, data_labels, data_items = batch
            label_tensors, data_tensors = label_tensors.to(device), data_tensors.to(device)

            y_pred = model(data_tensors, lengths)

            loss = criterion(y_pred, label_tensors)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
        train_loss /= len(train_loader)
        train_losses.append(train_loss)

        validate_loss = 0
        corrects = 0
        with torch.no_grad():
            model.eval()
            for batch in validate_loader:
                label_tensors, data_tensors, lengths, data_labels, data_items = batch
                label_tensors, data_tensors = label_tensors.to(device), data_tensors.to(device)

                y_pred = model(data_tensors, lengths)

                loss = criterion(y_pred, label_tensors)

                validate_loss += loss.item()

                preds = y_pred.argmax(dim=-1)

                corrects += (preds == label_tensors).sum().item()

        accuracy = corrects / len(validate_loader.dataset)
        validate_loss /= len(validate_loader)

        validate_accuracy.append(accuracy)
        validate_losses.append(validate_loss)

        print(f"Epoch:[{epoch + 1}/{epochs}], Train_loss = {train_loss: .4f} | Validate_loss = {validate_loss: .4f} | Accuracy = {accuracy: .4f}")

    return train_losses, validate_losses, validate_accuracy


def evaluate_model(model, test_loader, device):
    """
    使用 test_loader 评估模型，收集预测结果
    """
    model.eval()

    y_true = []
    y_pred = []

    with torch.no_grad():
        for batch in test_loader: # 直接遍历 DataLoader
            label_tensors, data_tensors, lengths, _, _ = batch
            label_tensors, data_tensors = label_tensors.to(device), data_tensors.to(device)

            # 模型前向传播（正确传入 lengths）
            outputs = model(data_tensors, lengths)

            # 提取预测标签 (Batch 操作)
            preds = outputs.argmax(dim=-1)

            # 将当前 batch 的真实标签和预测标签收集到列表中
            # .cpu().tolist() 将 GPU 上的 tensor 转换为普通的 Python 列表
            y_pred.extend(preds.cpu().tolist())
            y_true.extend(label_tensors.cpu().tolist())

    # 计算总精度
    accuracy = sum(int(t == p) for t, p in zip(y_true, y_pred)) / len(y_true) if y_true else 0.0

    print(f"Test Accuracy: {accuracy:.4f}\n")

    return y_true, y_pred, accuracy


def gen_find_files(path):
    return glob.glob(path)


def gen_unicode_to_ascii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn' and c in ALL_LETTERS
    )


def gen_read_lines(filename):
    with open(filename, encoding='utf-8') as some_file:
        return [gen_unicode_to_ascii(line.strip()) for line in some_file]


def gen_load_category_lines(data_dir):
    category_lines = {}
    all_categories = []
    for filename in gen_find_files(os.path.join(data_dir, '*.txt')):
        category = os.path.splitext(os.path.basename(filename))[0]
        all_categories.append(category)
        lines = gen_read_lines(filename)
        category_lines[category] = lines

    if not all_categories:
        raise RuntimeError(
            'Data not found. Make sure that you downloaded data '
            'from https://download.pytorch.org/tutorial/data.zip and extract it to '
            'the current directory.'
        )

    return category_lines, all_categories


def gen_split_category_lines(category_lines, val_ratio=0.1, seed=42):
    rng = random.Random(seed)
    train_lines = {}
    val_lines = {}
    for category, lines in category_lines.items():
        lines_copy = list(lines)
        rng.shuffle(lines_copy)
        split_idx = max(1, int(len(lines_copy) * (1 - val_ratio)))
        train_lines[category] = lines_copy[:split_idx]
        val_lines[category] = lines_copy[split_idx:] or lines_copy[:1]
    return train_lines, val_lines


def gen_random_choice(items):
    return items[random.randint(0, len(items) - 1)]


def gen_random_training_pair(category_lines, all_categories):
    category = gen_random_choice(all_categories)
    line = gen_random_choice(category_lines[category])
    return category, line


def gen_category_tensor(category, all_categories):
    li = all_categories.index(category)
    tensor = torch.zeros(1, len(all_categories))
    tensor[0][li] = 1
    return tensor


def gen_input_tensor(line):
    tensor = torch.zeros(len(line), 1, N_LETTERS)
    for li in range(len(line)):
        letter = line[li]
        tensor[li][0][ALL_LETTERS.find(letter)] = 1
    return tensor


def gen_target_tensor(line):
    letter_indexes = [ALL_LETTERS.find(line[li]) for li in range(1, len(line))]
    letter_indexes.append(N_LETTERS - 1)
    return torch.LongTensor(letter_indexes)


def gen_random_training_example(category_lines, all_categories):
    category, line = gen_random_training_pair(category_lines, all_categories)
    category_tensor = gen_category_tensor(category, all_categories)
    input_line_tensor = gen_input_tensor(line)
    target_line_tensor = gen_target_tensor(line)
    return category_tensor, input_line_tensor, target_line_tensor


def gen_collect_hidden_states(
    rnn,
    category_lines,
    all_categories,
    device,
    max_per_category=100,
    seed=42,
):
    rnn.eval()
    rng = random.Random(seed)
    hidden_states = []
    labels = []

    with torch.no_grad():
        for category in all_categories:
            lines = list(category_lines.get(category, []))
            if not lines:
                continue

            if max_per_category is not None and len(lines) > max_per_category:
                lines = rng.sample(lines, max_per_category)

            for line in lines:
                if not line:
                    continue
                category_tensor = gen_category_tensor(category, all_categories).to(device)
                input_line_tensor = gen_input_tensor(line).to(device)
                hidden = rnn.initHidden(device=device)

                for i in range(input_line_tensor.size(0)):
                    _, hidden = rnn(category_tensor, input_line_tensor[i], hidden)

                hidden_states.append(hidden.squeeze(0).cpu())
                labels.append(category)

    if not hidden_states:
        return [], []

    return torch.stack(hidden_states).numpy(), labels


def gen_evaluate_loss(rnn, category_lines, all_categories, criterion, device, n_samples=200):
    rnn.eval()
    total_loss = 0.0
    total_steps = 0

    with torch.no_grad():
        for _ in range(n_samples):
            category_tensor, input_line_tensor, target_line_tensor = gen_random_training_example(
                category_lines, all_categories
            )
            category_tensor = category_tensor.to(device)
            input_line_tensor = input_line_tensor.to(device)
            target_line_tensor = target_line_tensor.to(device)

            hidden = rnn.initHidden(device=device)
            target_line_tensor = target_line_tensor.unsqueeze(-1)
            for i in range(input_line_tensor.size(0)):
                output, hidden = rnn(category_tensor, input_line_tensor[i], hidden)
                l = criterion(output, target_line_tensor[i])
                total_loss += l.item()
                total_steps += 1

    if total_steps == 0:
        return 0.0
    return total_loss / total_steps


def gen_train_step(rnn, category_tensor, input_line_tensor, target_line_tensor, criterion, learning_rate):
    target_line_tensor = target_line_tensor.unsqueeze(-1)
    hidden = rnn.initHidden(device=category_tensor.device)

    rnn.zero_grad()

    loss = torch.zeros(1, device=category_tensor.device)

    for i in range(input_line_tensor.size(0)):
        output, hidden = rnn(category_tensor, input_line_tensor[i], hidden)
        l = criterion(output, target_line_tensor[i])
        loss += l

    loss.backward()

    for p in rnn.parameters():
        p.data.add_(p.grad.data, alpha=-learning_rate)

    return output, loss.item() / input_line_tensor.size(0)


def gen_time_since(since):
    now = time.time()
    s = now - since
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)


def train_char_rnn_generator(
    rnn,
    category_lines,
    all_categories,
    device,
    n_iters=100000,
    print_every=5000,
    plot_every=500,
    learning_rate=0.0005,
    val_category_lines=None,
    val_samples=200,
):
    criterion = nn.NLLLoss()
    train_losses = []
    val_losses = []
    total_loss = 0
    start = time.time()

    for iter in range(1, n_iters + 1):
        category_tensor, input_line_tensor, target_line_tensor = gen_random_training_example(
            category_lines, all_categories
        )
        category_tensor = category_tensor.to(device)
        input_line_tensor = input_line_tensor.to(device)
        target_line_tensor = target_line_tensor.to(device)

        _, loss = gen_train_step(
            rnn,
            category_tensor,
            input_line_tensor,
            target_line_tensor,
            criterion,
            learning_rate,
        )
        total_loss += loss

        if iter % print_every == 0:
            print('%s (%d %d%%) %.4f' % (gen_time_since(start), iter, iter / n_iters * 100, loss))

        if iter % plot_every == 0:
            train_losses.append(total_loss / plot_every)
            if val_category_lines is not None:
                val_loss = gen_evaluate_loss(
                    rnn,
                    val_category_lines,
                    all_categories,
                    criterion,
                    device,
                    n_samples=val_samples,
                )
                val_losses.append(val_loss)
            total_loss = 0

    return train_losses, val_losses


def sample_char_rnn(rnn, category, all_categories, start_letter='A', max_length=20, device=None):
    if device is None:
        device = next(rnn.parameters()).device

    with torch.no_grad():
        category_tensor = gen_category_tensor(category, all_categories).to(device)
        input_tensor = gen_input_tensor(start_letter).to(device)
        hidden = rnn.initHidden(device=device)

        output_name = start_letter

        for _ in range(max_length):
            output, hidden = rnn(category_tensor, input_tensor[0], hidden)
            topv, topi = output.topk(1)
            topi = topi[0][0].item()
            if topi == N_LETTERS - 1:
                break
            letter = ALL_LETTERS[topi]
            output_name += letter
            input_tensor = gen_input_tensor(letter).to(device)

        return output_name


def sample_char_rnn_group(rnn, category, all_categories, start_letters='ABC', max_length=20, device=None):
    outputs = []
    for start_letter in start_letters:
        outputs.append(sample_char_rnn(
            rnn,
            category,
            all_categories,
            start_letter=start_letter,
            max_length=max_length,
            device=device,
        ))
    return outputs