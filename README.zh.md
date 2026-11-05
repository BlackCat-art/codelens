# CodeLens

[![tests](https://github.com/BlackCat-art/codelens/actions/workflows/test.yml/badge.svg)](https://github.com/BlackCat-art/codelens/actions/workflows/test.yml)

[English](README.md)

零依赖工具:把 AI 生成的 Python 项目变成人类能读的“地图”,让你不借助 AI 也能看懂代码、定位问题、手动修复。

## 为什么需要它

AI 编程 Agent 写代码的速度远超人类阅读的速度。出问题时,人们习惯把报错再贴给 Agent,然后祈祷它改对。久而久之,没有人脑中还保存着整个系统的模型。CodeLens 只使用纯静态分析(Python 的 `ast` 模块,不调用大模型,不联网),给你带文件名和行号的事实,而不是猜测。

## 快速开始

需要 Python 3.9+,无需安装任何依赖包。

```bash
git clone https://github.com/BlackCat-art/codelens.git
cd codelens

# 1. 生成项目地图
python codelens.py map /path/to/your/project -o CODELENS.md

# 2. 追踪某个函数:谁调用了它,它又调用了谁
python codelens.py trace /path/to/your/project function_name -d 3
```

### 报告语言

报告支持中文和英文。用 `--lang zh` 或 `--lang en` 指定。默认是 `--lang auto`:当环境变量 `LC_ALL` 或 `LANG` 以 `zh` 开头时输出中文,否则输出英文。

```bash
python codelens.py map /path/to/your/project --lang zh
python codelens.py trace /path/to/your/project function_name --lang en
```

只有 CodeLens 自己生成的文字会被翻译。模块说明来自你代码里的 docstring,不会被翻译。

## 示例输出

下面的报告来自 [examples/demo](examples/demo) 里的一个小型“shop”演示项目,里面故意埋了几类 AI 常见问题。完整报告:[English](examples/CODELENS.example.en.md) | [中文](examples/CODELENS.example.zh.md)。

疑点清单(第 4 节,有删减):

- `shop.services.inventory:6` 吞掉异常(`except` 后什么都不做,bug 会被隐藏)
- `shop.services.inventory:9` 空实现函数 `reserve()`
- `shop.services.orders:11` 遗留的 `# TODO: handle out-of-stock properly`
- `shop.services.payment:2` 遗留的 `# placeholder: integrate real gateway`
- `shop.services.payment:7` 空实现函数 `refund_check()`
- `calc_total` 被定义了两次(`inventory` 和 `pricing`),很可能是重复实现

`check_stock` 的追踪结果,显示执行是怎么走到这里的(真实输出):

```
$ cd examples/demo
$ python ../../codelens.py trace . check_stock --lang zh

== shop.services.inventory.check_stock (./shop/services/inventory.py:3-7) 复杂度=2 ==
【谁调用了它(上游,找触发路径)】
└─ shop.services.orders.create_order (./shop/services/orders.py:4)
   └─ shop.app.main (./shop/app.py:4)
【它调用了谁(下游,找出错点)】
```

## 地图里有什么

- 入口:含 `__main__` 的模块,以及被装饰为路由或命令的函数。
- 模块表和 Mermaid 依赖图(粘贴到支持 Mermaid 的 Markdown 查看器里即可显示)。
- 高风险热点:按圈复杂度、函数长度和被调用次数排出前 10 个函数,建议优先阅读。
- AI 代码常见问题清单:空实现函数、被吞掉的异常(`except` 后什么都不做)、遗留的 TODO/FIXME/placeholder 注释,以及可能是重复实现的同名函数。
- 来自 `git log` 的最常被改动的文件,这些地方往往最容易出 bug。

## 用 `trace` 排查问题

`trace` 会为你指定的函数打印两棵树:

- 上游:谁调用了它,说明执行是如何到达出错代码的。
- 下游:它调用了谁,说明故障可能来自哪里。

每一行都带有 `path:line`,你可以在编辑器里手动顺着这条链排查。

## 局限

- 目前仅支持 Python。
- 调用关系按函数名匹配。动态调用、回调和同名函数可能造成误报或漏报。
- import 按你传入的目录来解析,请对项目的源码根目录运行 CodeLens。
- 这是静态分析,不知道运行时的值,也不理解业务意图。
- 热点评分的权重是经验值,尚未在大量真实项目上校准。

## 测试

```bash
pip install pytest
pytest
```

测试会在演示项目上分别用两种语言运行工具,检查疑点、依赖图、`trace` 输出,并确认中英文字符串表保持同步。

## 路线图

- 通过 tree-sitter 支持多语言(JS/TS、Go、Java)。
- 可交互的 HTML 报告,点击即可跳转到源码。
- 结合 `git blame`,标出 AI 编写且从未被人审查过的代码。
- 给出建议阅读顺序,并提供按模块记录设计意图的模板。
- 做成 pre-commit / CI 检查:复杂度超标或出现空实现时拦截。

## 参与贡献

欢迎提交 Issue 和 Pull Request。真实项目里的误报和漏报尤其有价值,请附上最小代码示例。

## 协议

MIT。详见 [LICENSE](LICENSE)。
