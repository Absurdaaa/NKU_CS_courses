好，这题**非常对路** 👍
计网期末里的 **socket 编程题**，通常不是考你写多复杂，而是考你**对通信流程 + API 语义是否清楚**。我按「**必考要点 → 常见坑 → 模板 → 练习题（含提示）**」来给你系统梳理一遍。

---

# 一、期末 Socket 编程题的「出题画像」

一般具有以下特点之一（或组合）：

* **TCP / UDP 二选一**
* **Client–Server 模型**
* 功能很简单：

  * 回显（echo）
  * 求和 / 统计
  * 字符串处理
* **不考高并发**
* **重流程、轻工程**
* 通常限制：

  * 单客户端
  * 阻塞 I/O
  * 不用多线程 / select

👉 **核心考察点**：

> 你是否理解「谁先调用什么」「每一步的作用是什么」

---

# 二、TCP Socket 编程：必会要点（⭐重点）

## 1️⃣ TCP 基本流程（必须背成条件反射）

### Server 端流程（顺序不能错）

```text
socket()
bind()
listen()
accept()
recv()/send()
close()
```

### Client 端流程

```text
socket()
connect()
send()/recv()
close()
```

📌 **考点**：

* `accept()` **会阻塞**
* `recv()` **可能返回 0**
* `listen()` 只在 server 用
* client **没有 bind 也能工作**

---

## 2️⃣ 关键 API 的“考试级理解”

### `socket()`

```c
int sockfd = socket(AF_INET, SOCK_STREAM, 0);
```

* `AF_INET` → IPv4
* `SOCK_STREAM` → TCP
* 返回的是 **文件描述符**

---

### `bind()`

```c
bind(sockfd, (struct sockaddr*)&addr, sizeof(addr));
```

📌 必考细节：

```c
addr.sin_addr.s_addr = INADDR_ANY;
addr.sin_port = htons(8080);
```

* `INADDR_ANY`：监听所有本机 IP
* `htons` / `htonl`：**一定要写**

  * 考试很喜欢扣这个

---

### `listen()`

```c
listen(sockfd, 5);
```

* 参数是 **等待队列长度**
* 不等于最大连接数（但考试一般不深究）

---

### `accept()`

```c
int connfd = accept(sockfd, NULL, NULL);
```

⚠️ **超级高频坑**：

* `accept()` 返回的是 **新的 socket**
* 原来的 `sockfd` 仍然用于监听

---

### `recv()` / `send()`

```c
n = recv(connfd, buf, sizeof(buf), 0);
```

* `n > 0`：收到数据
* `n == 0`：**对方关闭连接**
* `n < 0`：错误

📌 期末默认：

* 一次 `send` 对应一次 `recv`（不考虑粘包）

---

## 3️⃣ TCP 常见“期末必踩坑”

| 坑                     | 正确理解          |
| --------------------- | ------------- |
| recv 一定能收到完整消息        | ❌ 不保证（考试一般忽略） |
| accept 返回监听 socket    | ❌ 返回新 socket  |
| recv 返回 -1 表示对端关闭     | ❌ 返回 0        |
| server 不 close socket | ❌ 会资源泄漏       |
| 忘记 htons              | ❌ 直接扣分        |

---

# 三、UDP Socket 编程：考法很固定

## UDP 特点（期末重点）

* **无连接**
* **无 listen / accept**
* 一次 `sendto` 对应一次 `recvfrom`

---

### UDP 基本流程

#### Server

```text
socket()
bind()
recvfrom()
sendto()
close()
```

#### Client

```text
socket()
sendto()
recvfrom()
close()
```

📌 UDP 不用 `connect()`（可用但期末一般不用）

---

# 四、万能 TCP 模板（考试可直接套）

## TCP Server（精简版）

```c
int sockfd = socket(AF_INET, SOCK_STREAM, 0);

struct sockaddr_in addr;
addr.sin_family = AF_INET;
addr.sin_addr.s_addr = INADDR_ANY;
addr.sin_port = htons(8080);

bind(sockfd, (struct sockaddr*)&addr, sizeof(addr));
listen(sockfd, 5);

int connfd = accept(sockfd, NULL, NULL);

char buf[1024];
int n = recv(connfd, buf, sizeof(buf), 0);
send(connfd, buf, n, 0);

close(connfd);
close(sockfd);
```

---

## TCP Client（精简版）

```c
int sockfd = socket(AF_INET, SOCK_STREAM, 0);

struct sockaddr_in serv;
serv.sin_family = AF_INET;
serv.sin_port = htons(8080);
inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr);

connect(sockfd, (struct sockaddr*)&serv, sizeof(serv));

send(sockfd, "hello", 5, 0);
recv(sockfd, buf, sizeof(buf), 0);

close(sockfd);
```

---

# 五、期末【高频编程题】我给你准备 4 道（含提示）

---

## 🧪 题目 1（⭐⭐⭐最经典）

**TCP 回显服务器（Echo Server）**

要求：

* 客户端发送一行字符串
* 服务器原样返回
* 客户端打印后退出

👉 考点：

* TCP 基本流程
* recv/send
* accept 返回值

---

## 🧪 题目 2（⭐⭐）

**TCP 求和服务器**

* 客户端发送两个整数
* 服务器返回它们的和

📌 提示：

* 可以直接发送字符串 `"3 5"`
* server 用 `sscanf`

---

## 🧪 题目 3（⭐⭐⭐）

**UDP 大小写转换**

* 客户端发送字符串
* 服务器将小写转大写返回

📌 考点：

* `recvfrom` / `sendto`
* sockaddr 的使用

---

## 🧪 题目 4（⭐⭐⭐⭐加分题）

**TCP 文件行数统计**

* 客户端发送文本
* 服务器返回行数

📌 考点：

* 循环 `recv`
* 判断 `recv == 0`

---

# 六、考试最后 10 分钟的「保命 checklist」

进考场前默念一遍：

* TCP server：**socket → bind → listen → accept**
* client：**socket → connect**
* `accept` 返回新 socket
* `recv == 0` → 对方关闭
* 端口号一定 `htons`
* `INADDR_ANY`
* 记得 `close()`

---

如果你愿意，**下一步我可以直接“模拟一套期末真题”**：

* 给你 **完整题面**
* 限定 **20 分钟**
* 我来**按助教标准给你改 + 扣分点说明**

你只要说一句：
👉 **“来一套 TCP 真题” 或 “来一套 UDP 真题”**
