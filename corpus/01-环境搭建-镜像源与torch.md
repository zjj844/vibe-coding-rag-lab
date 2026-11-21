# 环境搭建：torch 安装与镜像源

现象：在本机 Python 3.13 环境下，用清华镜像执行 pip install torch 失败，提示找不到匹配的发行版。

排查过程：先用官方 PyPI 装一次，能装上，说明不是网络问题，而是清华镜像同步了 torch 的项目，但没有适配 cp313（Python 3.13）的二进制轮子。镜像只同步部分文件，Python 版本越新越容易缺。

解决方案：分层换源。常用纯 Python 依赖（requests、pandas）继续走清华镜像，速度快；torch 这类带二进制扩展的包单独指定官方 PyPI：pip install torch -i https://pypi.org/simple。

结论：遇到 find no matching distribution 时，先怀疑镜像同步不全，再怀疑版本号写错。
