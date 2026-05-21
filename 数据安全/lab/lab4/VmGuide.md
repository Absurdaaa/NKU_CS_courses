# VmGuide.md — FH-OPE 实验完整操作清单

> 所有开关都通过命令行参数控制，无需修改代码、无需重复编译。

---

# 一、虚拟机环境准备（Ubuntu）

## 1.1 把 lab4 目录拷进虚拟机

```bash
# 放在 ~/lab4/
ls ~/lab4/
# 确保看到: Node.h Node.cpp UDF.cpp fhope.sql client.py
```

## 1.2 安装 MySQL 与编译依赖

```bash
sudo apt update
sudo apt install -y mysql-server libmysqlclient-dev g++
```

**截图点 1**：`mysql --version` 和 `g++ --version`。

## 1.3 创建 MySQL 用户

```bash
sudo mysql
```

```sql
CREATE USER 'user'@'%' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON *.* TO 'user'@'%';
FLUSH PRIVILEGES;
EXIT;
```

验证：

```bash
mysql -uuser -p123456 -e "SELECT 1;"
```

**截图点 2**：输出 `1` 即连接成功。

## 1.4 安装 Python 依赖

```bash
sudo apt install -y python3 python3-pip
pip3 install pycryptodome pymysql
```

验证：

```bash
python3 -c "from Crypto.Cipher import AES; import pymysql; print('OK')"
```

**截图点 3**：输出 `OK`。

---

# 二、编译 UDF 并接入 MySQL（只做一次）

## 2.1 编译

```bash
cd ~/lab4
g++ -shared -fPIC UDF.cpp Node.cpp -o libfhope.so $(mysql_config --cflags) $(mysql_config --libs)
ls -l libfhope.so
```

**截图点 4**：编译无报错，libfhope.so 已生成。

## 2.2 安装插件 & 导入 SQL

```bash
sudo cp libfhope.so $(mysql_config --plugindir)/
sudo systemctl restart mysql

mysql -uuser -p123456 << 'EOSQL'
CREATE DATABASE IF NOT EXISTS test_db;
USE test_db;
SOURCE ~/桌面/lab4/fhope.sql;
SELECT FHStart(), FHEnd();
EOSQL
```

> 如果你的用户名不是 `$USER`，把 `/home/$USER/lab4/fhope.sql` 改成实际绝对路径。

**截图点 5**：`SELECT FHStart(), FHEnd();` 输出 `-1, -1`。

---

# 三、基本功能验证

## 3.1 单条插入

```bash
cd ~/lab4
python3 client.py --value apple --repeat 1 --seed 1
```

期望看到 `enc=<大整数>`、`recode=0`。

## 3.2 多样本插入 + 范围查询

```bash
cd ~/lab4
python3 -c "
import client as c
c.local_table = {}
c.key = c.get_random_bytes(16)
c.base_iv = c.get_random_bytes(16)
for fruit in ['apple', 'banana', 'cherry', 'date', 'apple', 'banana']:
    r = c.Insert(fruit)
    print(f'insert {fruit}: pos={r[\"pos\"]} enc={r[\"encoding\"]} recode={r[\"encoding\"]==0}')
print()
print('=== range query [banana, cherry] ===')
c.Search('banana', 'cherry')
"
```

期望：范围查询返回 `banana`、`cherry` 对应密文，且解密后明文正确。

**截图点 6**：范围查询输出。

---

# 四、核心实验：观察 recode 与 rebalance

## 开关说明

| 参数 | 作用 |
|------|------|
| `--debug` | 开启 C++ 侧日志（rebalance/recode 事件写入 MySQL error.log），运行结束打印 server 侧 rebalance 次数 |
| `--csv exp.csv` | 每轮插入的数据写入 CSV（供后续画图） |
| `--value apple` | 要插入的明文 |
| `--repeat 500` | 插入次数 |
| `--seed 1` | 随机种子 |
| `--report-every 0` | 不逐行打印（只看最终总结）。设为 1 则每行都打印 |

## 运行命令（每组实验前先重启 MySQL）

### 实验：不同 N 值 + full debug + CSV

```bash
# ==== 每次实验前必须执行 ====
sudo systemctl restart mysql
mysql -uuser -p123456 -e "TRUNCATE TABLE test_db.example;"

# ==== N=50 ====
cd ~/lab4
python3 client.py --value apple --repeat 50 --seed 1 --report-every 0 --debug --csv N50.csv

# ==== N=200 (先重启) ====
sudo systemctl restart mysql
mysql -uuser -p123456 -e "TRUNCATE TABLE test_db.example;"
python3 client.py --value apple --repeat 200 --seed 1 --report-every 0 --debug --csv N200.csv

# ==== N=500 (先重启) ====
sudo systemctl restart mysql
mysql -uuser -p123456 -e "TRUNCATE TABLE test_db.example;"
python3 client.py --value apple --repeat 500 --seed 1 --report-every 1 --debug --csv N500.csv 2>&1 | tee N500.log

# ==== N=2000 (先重启) ====
sudo systemctl restart mysql
mysql -uuser -p123456 -e "TRUNCATE TABLE test_db.example;"
python3 client.py --value apple --repeat 1000 --seed 1 --report-every 0 --debug --csv N2000.csv
```

**截图点 7**：N=500 运行时 `tee N500.log` 的输出，截取其中 `enc=0` 的行（几处即可）。

**截图点 8**：四组 N 值运行完毕后的总结行（包含 `recode=X` 和 `rebalance_cnt=Y`）。

### 查看 C++ 侧的 rebalance/recode 日志

```bash
sudo tail -1000 /var/log/mysql/error.log | grep FHOPE-DEBUG
```

输出示例：

```
[FHOPE-DEBUG] Debug logging enabled
[FHOPE-DEBUG] Recode: 2 nodes, 150 ciphers, interval=[0, 4611686018427387904)
[FHOPE-DEBUG] LeafNode rebalance, ciphers=128 total_global=0
[FHOPE-DEBUG] Recode: 3 nodes, 300 ciphers, interval=[0, 4611686018427387904)
...
```

- `LeafNode rebalance` → 叶子分裂
- `InternalNode rebalance` → 内部结点分裂
- `Recode` → 编码重分配

**截图点 9**：`grep FHOPE-DEBUG` 的输出，展示 rebalance 和 Recode 事件。

---

# 五、可视化（宿主机上做）

把虚拟机里的 CSV 文件拷到宿主机，然后：

```bash
cd ~/lab4
python3 plot_results.py
```

脚本会自动在同目录找 CSV 文件并生成 `results_N500.png` 等图片。

**截图点 10**：生成的图表（encoding 散点图+recode 红竖线+rebalance 绿虚线+update 行数柱状图）。

---

# 六、报告需要的数据

运行完上述命令后，收集以下信息填入报告：

| 插入次数 N | recode 次数 | rebalance 次数 | 备注 |
|-----------|-----------|---------------|------|
| 50 | ? | ? | |
| 200 | ? | ? | |
| 500 | ? | ? | |
| 2000 | ? | ? | |

外加：
- 范围查询正常运行的截图（截图点 6）
- N=500 时出现 enc=0 的终端截图（截图点 7）
- MySQL error.log 中 FHOPE-DEBUG 日志截图（截图点 9）
- 可视化图表（截图点 10）

---

# 七、常见问题

| 问题 | 解决方法 |
|------|---------|
| `Can't open shared library` | `sudo chmod 755 /usr/lib/mysql/plugin/libfhope.so` && `sudo systemctl restart mysql` |
| client.py 连接被拒 | `mysql -uuser -p123456 -e "SELECT 1"` 先确认用户可用 |
| recode 次数每次不一样 | 正常现象——CalPos 对重复值随机选择插入位置，用 `--seed` 固定 seed 即可复现 |
| --debug 看不到日志 | 确认 MySQL error.log 路径：`sudo ls /var/log/mysql/error.log` |
| 忘了重启 MySQL | 编码树在内存中不 reset，数据会叠加，务必重启 |
