# 系统库缺失：libGL.so.1

现象：跑 unstructured 的 partition_pdf，hi_res 策略直接崩溃，报 ImportError: libGL.so.1: cannot open shared object file。

排查：先确认 Python 包已经装好，再看报错里的 .so.1 后缀——这是 Linux 动态链接库，属于操作系统层面的库，不在 Python 包的管辖范围里。

解决方案：用系统包管理器安装，而不是 pip。Debian 或 Ubuntu 上执行 apt-get update 然后 apt-get install -y libgl1。pip 里没有任何包能提供 libGL.so.1。

结论：报错里出现 .so 文件缺失，一律先想系统库，用 apt 装；pip 只管 Python 包。

同类坑：libglib2.0-0、libsm6、libxext6 也常常缺失。
