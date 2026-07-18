# Clover 论文方法流程与结论梳理

本文档用于后续继续制作 HTML 幻灯片。内容以论文原文为准，重点整理 Clover 的问题、方法流程、关键机制、实验结论和适合放进 PPT 的表达方式。

## 1. 论文基本信息

- 论文题目：Harnessing Sparsification in Federated Learning: A Secure, Efficient, and Differentially Private Realization
- 系统名称：Clover
- 作者：Shuangqing Xu, Yifeng Zheng, Zhongyun Hua
- 会议：ACM CCS 2025
- arXiv：2511.07123
- DOI：10.1145/3719027.3765044
- 本地 PDF：[ref/clover-paper.pdf](ref/clover-paper.pdf)

## 2. 一句话主线

Clover 解决的是：在联邦学习中继续使用标准 top-k 梯度稀疏化以降低通信成本，同时隐藏每个客户端的 top-k index 和 value，并对最终模型提供差分隐私保证。

适合 PPT 的一句话：

> Clover keeps top-k sparsification, but hides both selected indices and values during secure aggregation, and adds distributed DP noise to protect the final model.

中文表达：

> Clover 保留 top-k 稀疏化带来的通信优势，同时隐藏每个客户端选中的位置和值，并通过分布式噪声为最终模型提供差分隐私。

## 3. 为什么需要 Clover

### 3.1 联邦学习的通信瓶颈

标准联邦学习每轮需要客户端上传高维梯度或模型更新。现代模型维度很高，客户端数量多时，通信成本成为瓶颈。

top-k sparsification 是常用优化：每个客户端只上传绝对值最大的 k 个梯度分量。因为 k 远小于模型维度 d，所以可以显著降低客户端到服务器的通信量。

### 3.2 top-k 带来的隐私问题

top-k 稀疏更新包含两类敏感信息：

- value：被选中坐标上的梯度值。
- index：哪些坐标被选中。

论文强调，index 本身也可能泄露客户端本地数据特征。即使 value 被加密或隐藏，如果服务器能看到每轮 top-k index，也可能进行推断。

适合 PPT 的表达：

```text
Top-k saves communication,
but selected indices become a privacy signal.
```

### 3.3 普通安全聚合不够

传统 secure aggregation 更适合聚合 dense vector。top-k 稀疏化下，不同客户端选择的 index 不同。若要求所有客户端使用相同 index，会破坏标准 top-k 的效果；若直接对 index-value pair 做通用 ORAM/安全计算，服务器侧开销很高。

因此 Clover 的核心问题是：

```text
Can we correctly aggregate sparse top-k updates
while hiding both values and indices?
```

中文：

```text
能否在隐藏 value 和 index 的同时，
正确聚合多个客户端的 top-k 稀疏更新？
```

## 4. 系统与威胁模型

### 4.1 三服务器分布式信任

Clover 使用三个服务器 `S0, S1, S2`。客户端不把明文 top-k 更新交给单个服务器，而是把数据编码并秘密分享给三个服务器。

核心直觉：

- 单个服务器只能看到 share。
- 多个服务器协作完成聚合。
- 服务器最终只恢复带 DP 噪声的聚合结果。

### 4.2 威胁假设

论文考虑三服务器设置下的非合谋、诚实多数模型：

- 每个服务器可能试图从协议执行中推断客户端隐私。
- 至多一个服务器可能恶意偏离协议。
- Clover 目标是让服务器学不到单个客户端的稀疏更新，并在恶意服务器破坏计算时检测并 abort。

PPT 可以简化为：

```text
Assumption: three non-colluding servers, honest majority.
Goal: no single server learns individual top-k indices or values.
```

## 5. Clover 总流程

一次训练轮次可以拆成以下步骤。

1. 服务器广播当前全局模型。
2. 客户端在本地数据上训练，得到梯度更新。
3. 客户端执行 top-k sparsification，只保留绝对值最大的 k 个分量。
4. 客户端通过 SparVecAgg 编码稀疏向量，并把 shares 发给三个服务器。
5. 三个服务器通过 secret-shared shuffle 恢复每个客户端稀疏向量的 secret-shared dense form。
6. 服务器在秘密分享域里对所有客户端更新求和，得到聚合梯度 share。
7. 服务器用分布式噪声生成机制加入 DP noise。
8. 服务器重构 noisy aggregate，并更新全局模型。

适合 HTML 页的流程：

```text
Local training
  -> Top-k sparsification
  -> SparVecAgg secure sparse aggregation
  -> Distributed DP noise
  -> Noisy global update
```

## 6. SparVecAgg 的输入与输出

### 6.1 输入

每个客户端 `C_i` 有一个 d 维稀疏向量 `x_i`。其中只有 k 个非零值。非零位置集合记为 `I_i`。

可以理解为：

```text
x_i[j] = gradient value, if j is selected by top-k
x_i[j] = 0, otherwise
```

### 6.2 输出

三个服务器得到聚合向量的 secret-shared form：

```text
JxK where x = sum_i x_i
```

服务器不应该看到任何单个客户端的：

- 非零 value。
- 非零 index。
- 完整稀疏向量。

## 7. SparVecAgg 核心思想

论文的关键洞察是：不要把 `(index, value)` 作为 secret-shared pair 再用 ORAM 写入，而是把稀疏向量重新编码成：

```text
前 k 个非零 value + 一个 permutation
```

具体地，客户端把非零值搬到向量前面，得到 `x_i'`。然后构造 permutation `π_i`，满足：

```text
x_i = π_i(x_i')
```

这样，原来“把 value 写回 index”的问题，变成了：

```text
在秘密分享域里，对 x_i' 应用隐藏的 permutation π_i。
```

这一步由 secret-shared shuffle 完成。

## 8. SparVecAgg 详细流程

### 8.1 找到非零位置和零位置

客户端扫描稀疏向量 `x_i`：

- `L_i`：非零元素位置列表，按出现顺序排列。
- `E_i`：零元素位置列表，按升序排列。

例如：

```text
x = [0, x1, 0, x3, 0, x5, 0, 0]
L = [1, 3, 5]
E = [0, 2, 4, 6, 7]
```

### 8.2 compact 非零值

客户端构造 `x_i'`：

```text
x' = [x1, x3, x5, 0, 0, 0, 0, 0]
```

也就是前 k 个位置放非零值，后面补零。

PPT 表达：

```text
Original sparse vector:
[0, x1, 0, x3, 0, x5, 0, 0]

Compacted vector:
[x1, x3, x5, 0, 0, 0, 0, 0]
```

### 8.3 构造真实 permutation `π_i`

`π_i` 把 compact 后的 `x_i'` 映射回原始位置：

```text
π_i(j) = L_i(j),        for 0 <= j < k
π_i(j) = E_i(j - k),    for k <= j < d
```

直观理解：

- 前 k 个 value 应该回到原来的非零位置。
- 后面的零回到原来的零位置。

所以：

```text
x_i = π_i(x_i')
```

### 8.4 不直接上传 `π_i`

如果客户端直接上传 `π_i`，服务器就能看出 top-k index。因为 `π_i` 的前 k 项就是非零值要回到的位置。

因此 Clover 不上传明文 `π_i`，而是把 `π_i` 分解成三个 permutation shares：

```text
π_i = π_i,0 ∘ π_i,1 ∘ π_i,2
```

其中：

- `π_i,0` 和 `π_i,1` 是客户端随机采样的 permutation。
- `π_i,2 = π_i,1^{-1} ∘ π_i,0^{-1} ∘ π_i`。

两个随机 permutation 相当于掩码。单看其中一部分，无法恢复真实的 `π_i`。

### 8.5 permutation compression

直接 secret-share 完整 permutation 会带来 `O(d)` 客户端通信。论文进一步压缩 permutation。

压缩方式：

1. `π_i,0` 和 `π_i,1` 是随机采样的 permutation，因此可以用 PRG seed 表示。
2. `π_i,2` 只有前 k 项影响非零 value 的位置；后面 `d-k` 项只是 shuffle zeros，没有实际信息。
3. 客户端只上传 `π_i,2` 的前 k 项，论文记为 `P_i`。

服务器收到 `P_i` 后，用补集 `R_i` 补齐：

```text
π_i,2'(j) = P_i(j),       for 0 <= j < k
π_i,2'(j) = R_i(j - k),   for k <= j < d
```

即使 `π_i,2'` 不完全等于客户端原来的 `π_i,2`，它对 `x_i'` 的效果相同，因为后面的元素全是 0。

### 8.6 客户端实际发送什么

对每个客户端，发送内容大致包括：

- `r_i`：compact 后前 k 个非零 value 的 secret shares。
- `s_i,0`：生成 `π_i,0` 的 PRG seed。
- `s_i,1`：生成 `π_i,1` 的 PRG seed。
- `P_i`：`π_i,2` 的前 k 项。

论文中的分发方式是：

```text
S0 gets seeds related to π_i,0 and π_i,1
S1 gets seed π_i,1 and P_i
S2 gets seed π_i,0 and P_i
```

不同服务器只拿到足够参与协议的部分信息，但单个服务器无法恢复真实 top-k index。

## 9. secret-shared shuffle 如何用

服务器端先做：

```text
Jx_i'K = Jr_iK || J0, ..., 0K
```

也就是把前 k 个 value 的 shares 后面补上 `d-k` 个 secret-shared zeros。

然后服务器依次应用 permutation shares。论文中的顺序是对 `π_i,1`、`π_i,0`、`π_i,2` 相关 shares 进行 secret-shared shuffle，使最终得到：

```text
Jx_iK = Jπ_i(x_i')K
```

核心安全点：

- shuffle 发生在 secret sharing 域里。
- 服务器看不到被洗牌的数据。
- 服务器也看不到完整 permutation。
- 没有单个服务器能看到全部 `π_i,0`、`π_i,1`、`π_i,2`。

得到每个客户端的 `Jx_iK` 后，服务器直接在 shares 上求和：

```text
JxK = sum_i Jx_iK
```

## 10. 为什么比 ORAM 更高效

ORAM strawman 的思路是：

```text
对每个 secret-shared (index, value)，
在 secret-shared dense vector 上执行 oblivious write。
```

问题是，每个 index-value pair 都要对高维向量执行昂贵的 oblivious write。

Clover 的思路是：

```text
把所有非零值 compact，
把 index 信息编码成 permutation，
用 secret-shared shuffle 一次性恢复位置。
```

因此，Clover 避免了对每个非零元素执行一次通用 ORAM 写入。

PPT 表达：

```text
ORAM baseline:
hide every write to index j

Clover:
encode all indices as a permutation,
then apply one secret-shared shuffle
```

## 11. 分布式差分隐私噪声

安全聚合只保护单个客户端更新；聚合结果和最终模型仍可能泄露信息。因此 Clover 还加入 DP noise。

论文不采用昂贵的 secure noise sampling，而是使用分布式噪声生成：

1. 每个服务器本地采样一个校准后的 discrete Gaussian noise。
2. 每个服务器把自己的 noise secret-share 给其他服务器。
3. 服务器在 secret sharing 域里把噪声加到聚合梯度上。
4. 最终重构的是 noisy aggregate。

直觉：

```text
单个服务器不能完全控制或移除总噪声；
聚合结果带有 DP noise；
最终模型满足 DP 保证。
```

## 12. 恶意服务器安全

论文不仅考虑 semi-honest 服务器，还考虑最多一个服务器恶意偏离协议。

需要检查三类问题：

1. permutation shares 是否正确解压和应用。
2. secret-shared shuffle 是否正确执行。
3. DP noise 是否正确采样并加入。

### 12.1 shuffle 完整性

论文使用 blind MAC verification：

- 客户端为重排后的稀疏更新生成 MAC。
- MAC key 也被 secret-shared。
- 服务器在 shuffle 时同时 shuffle 梯度 share 和 MAC key share。
- shuffle 后用 secure dot product 验证 MAC。
- 多个客户端的 MAC 可以 batch verify。

目的：

```text
如果恶意服务器错误解压 permutation 或错误执行 shuffle，
最终 shares 会不一致，MAC 检查会失败。
```

### 12.2 noise 正确性

恶意服务器可能采样错误噪声，影响模型效果。论文用 Kolmogorov-Smirnov test 检查噪声分布。

核心思想：

- 一个服务器采样噪声。
- 另一个服务器采样同分布噪声并分享。
- 第三个服务器重构二者之和。
- 对和分布执行 KS test，检查是否符合目标分布。

这样避免昂贵 MPC noise sampling，同时约束恶意噪声操作。

## 13. 实验结论

### 13.1 模型效果

论文实验显示，Clover 的模型效用接近 vanilla FL with central DP。也就是说，虽然引入了 top-k sparsification、安全聚合和分布式 DP noise，但最终训练效果仍然可用。

PPT 表达：

```text
Utility stays close to vanilla FL with central DP.
```

### 13.2 系统效率

论文报告：在 semi-honest setting 下，安全聚合 100 个维度为 `10^5`、密度为 `1%` 的稀疏向量时，SparVecAgg 相比 distributed ORAM baseline：

- inter-server communication 最高减少约 `1602x`。
- server-side computation 最高减少约 `12041x`。

PPT 表达：

```text
Against distributed ORAM baseline:
up to 1602x less inter-server communication
up to 12041x less server-side computation
```

### 13.3 恶意安全开销

相比 semi-honest 版本，malicious secure extension：

- 客户端到服务器通信几乎没有额外开销。
- 服务器间通信约 `2.67x`。
- 服务器端运行时间最多约 `3.67x`。

这个结论适合说明：完整性增强不是免费的，但开销相对可控。

### 13.4 DP sparse vector summation

论文还用 synthetic sparse vector summation 评估 DP 下的聚合误差。结论是：

- privacy budget `epsilon` 越大，噪声越小，MSE 越低。
- 在固定 epsilon 下，MSE 基本不随稀疏密度 `lambda` 变化，因为协议能正确聚合非零元素，误差主要来自 DP noise。

## 14. 适合后续 HTML 页的讲法

### 第 10 页：SparVecAgg 机制

建议表达为：

```text
SparVecAgg: Random permutation masks hide top-k indices
```

四步：

1. 原始 sparse vector：index 暴露风险。
2. compact：只把非零 value 收到前面。
3. random permutation masks：`π = π0 ∘ π1 ∘ π2`，只发送 `π2` 的前 k 项。
4. secret-shared shuffle：服务器在 shares 上恢复位置并聚合。

### 第 11 页：为什么高效

可以做 ORAM vs Clover 对比：

```text
ORAM: hide k individual writes
Clover: encode all indices as one permutation
```

视觉建议：

- 左边：每个 `(index,value)` 都要 ORAM write，很重。
- 右边：compact values + masked permutation + shuffle，一次性处理。

### 第 12 页：DP noise

可以讲：

```text
Secure aggregation protects individual updates.
DP noise protects the released aggregate/model.
```

视觉建议：

- 聚合结果 share。
- 三台服务器各自采样 noise。
- noise shares 加到 aggregate shares。
- 只释放 noisy aggregate。

### 第 13 页：恶意服务器完整性

可以讲：

```text
Malicious security checks whether shuffle and noise were done correctly.
```

视觉建议：

- permutation/shuffle check：blind MAC。
- noise check：KS test。
- aggregation check：hash/reconstruction consistency。

### 第 14 页：实验结论

建议三张卡：

1. Utility：接近 central DP baseline。
2. Efficiency：1602x / 12041x against ORAM baseline。
3. Robustness：malicious security overhead is moderate。

## 15. 需要避免的错误表述

不要说：

```text
客户端直接把 permutation secret-share 给服务器。
```

更准确地说：

```text
客户端将 permutation 分解为随机 permutation shares，并用 PRG seed 与 distillation 压缩传输。
```

不要说：

```text
服务器恢复每个客户端的 dense vector。
```

更准确地说：

```text
服务器得到每个客户端 dense vector 的 secret-shared form，用于后续聚合。
```

不要说：

```text
Clover 比普通 FL 更快。
```

更准确地说：

```text
Clover 在提供安全聚合和 DP 的前提下，比 distributed ORAM baseline 高效得多，并保持接近 central DP FL 的模型效用。
```

## 16. 汇报时的核心结论

Clover 的贡献不是单独提出 top-k、secure aggregation 或 DP，而是把三者放进一个系统里，并为 top-k 稀疏向量聚合设计了专门机制。

最终可以这样收束：

> Clover shows that top-k sparsification can be made compatible with secure aggregation and differential privacy, if index information is encoded as masked permutations rather than handled as explicit secret-shared indices.

中文：

> Clover 证明了 top-k 稀疏化并不一定和安全聚合、差分隐私冲突；关键是不要把 index 当作普通明文字段处理，而是把位置关系编码成随机掩码后的 permutation，再在秘密分享域里完成 shuffle 和聚合。
