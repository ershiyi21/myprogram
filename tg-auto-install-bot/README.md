# tg-auto-install-bot
一个简单的自动转存文件的telegram机器人，直接将消息转发给机器人，机器人自动提取文件，不限速下载消息中所有文件到本地，然后调用rclone上传文件到云端，完成后回复"xx文件下载完成+alist等列表程序访问该文件的地址"的消息（10分钟后删除该条回复的消息）。需借助自建的telegram bot api，官方api有文件大小限制.

[使用方法](https://www.yetpage.com/archives/430).
