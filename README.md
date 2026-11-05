# CodeLens
零依赖工具:把 AI 生成的 Python 项目变成人类能读的“地图”。

- `python codelens.py map ./proj` 生成 CODELENS.md:入口、模块依赖图(Mermaid)、高风险热点、AI常见坑、高频改动文件
- `python codelens.py trace ./proj 函数名` 查看上游触发路径与下游调用,手动定位 bug

局限:基于静态分析,按函数名匹配调用(动态调用/同名函数可能有误报)。目前仅支持 Python。
License: MIT
