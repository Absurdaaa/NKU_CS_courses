# FH-OPE（Frequency-Hiding OPE）复现步骤与代码整理

本文件根据 [提取自数据安全与隐私计算基础.docx](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/ref/提取自数据安全与隐私计算基础.docx) 中的“6.3.3 FH-OPE 实现”内容整理，并结合本次作业要求 [作业要求.md](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/作业要求.md) 做了结构化归纳与少量明显笔误修正（如包名、SQL 过程语法、动态库文件名一致性）。

## 作业目标

- 复现教材 6.3.3 的 FH-OPE（频率隐藏 OPE）实现流程
- 在 `client.py` 中修改测试逻辑：持续插入相同明文多次，观察编码树的分裂与编码更新（recode/update 区间）

## 目录与代码文件

- Server 侧（MySQL UDF + 编码树）
  - [Node.h](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/Node.h)
  - [Node.cpp](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/Node.cpp)
  - [UDF.cpp](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/UDF.cpp)
  - [fhope.sql](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/fhope.sql)
- Client 侧（随机加密 + 位置计算 + 调用存储过程）
  - [client.py](file:///Users/linshangjin/NKU_CS_courses/数据安全/lab/lab4/client.py)

## 1. 环境准备（按教材原文思路）

### 1.1 MySQL 安装与配置（以 Ubuntu 为例）

- 安装 MySQL 与开发组件（用于编译 UDF）：

```bash
sudo apt install mysql-server libmysqlclient-dev
```

- 进入 MySQL（root）：

```bash
sudo mysql
```

- 创建用户（示例）：

```sql
CREATE USER 'user'@'%' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON *.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

- 创建数据库（示例）：

```sql
CREATE DATABASE test_db;
```

### 1.2 Python3 环境（Ubuntu）

```bash
sudo apt install python3 python3-pip
pip3 install pycryptodome pymysql
```

## 2. Server 端：FH-OPE 编码树与 MySQL UDF

### 2.1 编码树（Node.h / Node.cpp）

- 主要结构是一个多叉树（内部结点记录各孩子包含的元素数量），叶子结点保存密文与对应编码区间 `[lower, upper)`。
- 当叶子中相邻编码间隔不足（`right-left < 2`）时触发 recode，计算一个更新区间 `[start_update, end_update)` 并生成 `update[cipher] = new_code` 映射，供数据库同步更新编码。
- 叶子容量达到 `M=128` 时进行结点分裂（rebalance）。

### 2.2 MySQL UDF（UDF.cpp）

UDF 提供 5 个函数：

- `FHInsert(pos, ct) -> BIGINT`：插入并返回编码；若返回 0 表示发生 recode，需要同步更新数据库中一段区间的编码
- `FHSearch(pos) -> BIGINT`：返回第 `pos` 个元素对应编码（用于范围查询边界）
- `FHUpdate(ct) -> BIGINT`：若 ct 在 `update` 映射中则返回新编码，否则返回 0
- `FHStart() / FHEnd()`：返回更新区间左右端点

## 3. 编译生成动态库（UDF 插件）

教材文本里出现了 `libope.so / libfhope.so` 等不一致命名。这里统一使用 `libfhope.so`（与 SQL 中 `SONAME` 保持一致）。

示例编译命令（Ubuntu + g++）：

```bash
g++ -shared -fPIC UDF.cpp Node.cpp -o libfhope.so
```

将动态库复制到 MySQL 插件目录（路径依发行版可能不同）：

```bash
sudo cp libfhope.so /usr/lib/mysql/plugin/
```

## 4. 导入 MySQL：表、函数与存储过程

1) 登录并进入数据库：

```bash
mysql -uuser -p123456
```

```sql
USE test_db;
```

2) 执行 SQL 脚本（绝对路径）：

```sql
SOURCE /absolute/path/to/fhope.sql;
```

`fhope.sql` 会：

- 创建 `example(encoding, ciphertext)` 表
- 注册 UDF 函数
- 创建存储过程 `pro_insert(pos, ct)`：插入一条密文；若 `FHInsert` 返回 0 则对更新区间内（以及编码为 0 的新插入行）执行一次 `UPDATE ... SET encoding = FHUpdate(ciphertext)`

## 5. Client 端：插入与范围查询（client.py）

运行：

```bash
python3 client.py
```

核心逻辑：

- 使用随机化 AES-CBC 对明文加密（同一明文每次加密得到不同密文）
- client 维护本地 `local_table`，对重复值随机选择插入位置，从而隐藏频率信息
- 插入通过 `CALL pro_insert(pos, ciphertext)` 完成
- 查询通过 `FHSearch(left_pos/right_pos)` 得到编码边界，再在 `example` 表里做范围过滤

## 6. 作业测试建议：持续插入相同值

作业要求是“在 client.py 中修改，不断插入相同数值多次，观察编码树分裂和编码更新”。建议做法：

- 在 `__main__` 里把插入列表改成例如 `['apple'] * 500` 或更大
- 每次插入后可以额外打印：
  - 当前插入的 pos
  - `FHInsert` 的返回值是否为 0（意味着发生 recode）
  - 更新区间 `[FHStart(), FHEnd())` 的变化（可在 MySQL 侧查询或在 UDF 内部调试输出）

