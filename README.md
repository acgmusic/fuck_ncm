脚本根据[ncmdump](https://github.com/QCloudHao/ncmdump)进行了修改，添加了自动提取封面的功能，以及命令行操作的方法

功能：将目录下的ncm文件全部转成mp3，同时下载封面，并添加到mp3文件中

请先安装依赖库：

```cmd
pip install pycrytodome
pip install eyed3
```

使用方法：命令行cd到文件目录，然后输入如下代码，其中`your_file_path`为ncm文件所在文件夹。输出mp3路径在同目录的`output`文件夹下。

```cmd
python fuck_ncm.py -p your_file_path
```

注意事项：本脚本仅供学习，请在下载后24小时内删除。
