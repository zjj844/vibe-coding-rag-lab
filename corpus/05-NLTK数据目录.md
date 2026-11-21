# NLTK 数据目录结构约定

现象：nltk 明明下载过资源，运行时仍然报 LookupError: Resource punkt not found。

原因：NLTK 的数据目录结构和资源名不是一一对应的。分句模型 punkt 必须放在 taggers/punkt 这样的层级下，而不是直接丢在 nltk_data 根目录。

约定：taggers 放标注模型，tokenizers 放分词模型，corpora 放语料，每个资源名是下一级目录。

解决方案：用 nltk.download 指定 download_dir 下载，或者手动按上面的层级摆好，再用 nltk.data.path 确认搜索路径包含你的目录。

结论：报 LookupError 时先查目录层级，再查下载是否成功；把 nltk.data.path 打印出来最直观。
