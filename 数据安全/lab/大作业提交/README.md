# Clover HTML 幻灯片说明

本目录包含数据安全课程论文汇报材料，主题为：

**Harnessing Sparsification in Federated Learning: A Secure, Efficient, and Differentially Private Realization**

## 文件说明

- `clover_demo.html`：HTML 幻灯片主入口。
- `clover_demo_single.html`：单文件 HTML 幻灯片版本，已内联所有页面内容，可以直接双击打开。
- `slides/`：幻灯片分页面文件，`clover_demo.html` 会动态加载这些页面。
- `clover_demo.pdf`：由 HTML 幻灯片导出的 PDF 版本。
- `7月4日(2).mp4`：汇报/演示视频文件。

## 推荐打开方式

如果希望直接双击打开，请使用：

```text
clover_demo_single.html
```

该文件是单文件版本，不依赖 `slides/` 目录，适合提交后直接查看。

`clover_demo.html` 是分文件版本，会使用 `fetch()` 加载 `slides/` 目录下的分页面文件。直接用 `file://` 方式打开时，部分浏览器会因为本地文件访问限制导致页面空白。

如果需要打开分文件版本，请在当前目录启动一个本地静态服务器后访问：

```bash
python3 -m http.server 8000
```

然后在浏览器中打开：

```text
http://127.0.0.1:8000/clover_demo.html
```

如果 8000 端口已被占用，可以换用其他端口，例如：

```bash
python3 -m http.server 8017
```

对应访问：

```text
http://127.0.0.1:8017/clover_demo.html
```

## 操作方式

- 右方向键、空格键、PageDown：下一页。
- 左方向键、PageUp：上一页。
- Home：跳到第一页。
- End：跳到最后一页。
- 也可以点击页面或底部按钮切换幻灯片。

## 注意事项

若提交单文件版本，只需要提交 `clover_demo_single.html` 即可直接查看。若提交分文件版本，请保持 `clover_demo.html` 与 `slides/` 文件夹位于同一目录下，否则 HTML 幻灯片无法加载分页面内容。若无法运行本地服务器，也可以直接查看 `clover_demo.pdf`。
