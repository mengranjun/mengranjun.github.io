把视频文件放进这个文件夹（比如 demo.mp4）。

然后用文本编辑器打开 posts/video.md，把这一行的文件名改掉：

    <video controls playsinline preload="metadata" src="../video/xxx.mp4"></video>

改完在项目根目录运行：

    python build.py

再刷新 posts/video.html 就能看到了。
