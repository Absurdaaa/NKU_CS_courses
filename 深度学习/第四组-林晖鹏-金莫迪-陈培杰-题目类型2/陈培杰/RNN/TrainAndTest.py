import torch
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