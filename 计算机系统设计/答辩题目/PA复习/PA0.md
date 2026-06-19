# PA0 — 开发环境配置

## 核心内容（考点较少，了解即可）

### Docker 工作流
```bash
docker build -t ics-image .      # 构建镜像
docker create --name=ics-vm -p 20022:22 ics-image
docker start ics-vm
ssh -p 20022 username@127.0.0.1  # 登录容器
```

### Git 分支工作流
```bash
git checkout -b pa1   # 新建分支
# ... 开发 ...
git add . && git commit --allow-empty
git checkout master
git merge pa1         # 合并到 master
```

### 编译运行 NEMU
```bash
cd nemu/
make          # 编译
make run      # 运行（会报 assertion fail，PA1 修复）
make gdb      # 用 GDB 调试 NEMU
make clean    # 清除编译结果
```

### 初始化子项目
```bash
git branch -m master
bash init.sh   # 拉取 nemu/nexus-am/nanos-lite/navy-apps
```
