import requests
import os
import shlex
import subprocess
import logging
import re
import time
import string
import threading
import concurrent.futures

## 全局变量

## Telegram Bot的令牌token
bot_token = "1111:aaaa"  

## 文件的本地保存地址，使用的是硬链接文件；若开启rclone上传，则为rclone上传时的文件中转地址
## 注意须与telegram-bot-api的文件下载位置【默认/var/lib/telegram-bot-api】位于同一硬盘，不然硬链接会失败
## 如存在文件跨盘移动，则需要通过开启rclone上传实现
## download_path 目录无需提前创建，程序运行后会自动创建
download_path = "/media/tgmedia/"  

## 是否开启crlone上传，True/False；如不开启上传，不需要安装rclone，文件保存在 download_path
enable_upload = True 

## rclone上传文件的远程路径，默认为rclone move，上传完成会删除 download_path 目录下的本地文件; e.g. /media/tg转存  onedrive:/
remote_path = ""

## 不需要修改,实际的Telegram Bot Api请求地址，只能使用自建api
api_base_url = "http://127.0.0.1:8081/bot" 

## 不需要修改,日志记录文件，实时查看日志最后200行，tail -f -n 200 /tmp/tg-auto-install-bot.log
logging_file = "/tmp/tg-auto-install-bot.log" 

## 允许的用户或者群组ID列表，多个用英文逗号隔开
allowed_user_ids = [aaaa, bbbb,-cccc,-dddd]  

## 不需要修改，定义清理旧数据的时间间隔（以秒为单位）
cleanup_interval = 3600  

## alist等列表程序，远程云盘对应remote_path的目录，回复消息时用的link拼接
remote_url = "http://url" 

## telegram-bot-api远端请求可重复次数，每一次为30s，超过次数则该文件下载失败
max_retries=200

## 请求telegram-bot-api的间隔时间，搭配max_retries使用。如网速很慢，调高max_retries即可
retry_delay=5

## 调用yt-dlp下载视频，默认关闭，True/False；如启用请安装导入yt-dlp以及安装ffmpeg
## yt-dlp一键安装脚本，bash <(curl -L -s https://raw.githubusercontent.com/ershiyi21/myprogram/main/yt/yt_install.sh)
## 视频选集链接必须指定p，在末尾添加 &p=1，不然会出错；尤其是b站
ytdlp = False

## 删除信息的默认时间，无需修改
time_sleep = 600
link_url = None

media_group_id_start_count = {}
media_group_id_end_count = {}

# 创建线程池
pool = concurrent.futures.ThreadPoolExecutor(max_workers=3) # 处理tg文件时的并发线程数，默认为3

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',filename=logging_file)
logger = logging.getLogger(__name__)

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"已创建目录：{directory}")

def create_empty_file(file_path):
    # 自动创建目录
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    # 创建空文件（不覆盖已有内容）
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8"):
            pass
        logger.info(f"已创建空白文件：{file_path}")
        return True
    else:
        logger.info(f"文件已存在：{file_path}")
        return False

def format_size(size):
    # 格式化文件大小显示
    size = float(size)
    if size < 1024:
        return f"{size:.2f} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 ** 3:
        return f"{size / (1024 ** 2):.2f} MB"
    else:
        return f"{size / (1024 ** 3):.2f} GB"

def send_reply(chat_id, message_id, text, time_sleep, link_url):

    
    url = f"{api_base_url}{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "reply_to_message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true"
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        reply_message_id = data["result"]["message_id"]  # 提取回复消息的 message_id
        logger.info(f"tg回复消息id {message_id} 成功！")
        
        #删除回复的消息
        thread = threading.Thread(target=delete_latest_message, args=(chat_id, reply_message_id, time_sleep))
        thread.start()
    else:
        logger.info(f"tg回复消息id {message_id} 失败！")
    
   
   
def delete_latest_message(chat_id, message_id, time_sleep):
    time.sleep(time_sleep)
    url = f"{api_base_url}{bot_token}/deleteMessage"
    params = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        logger.info(f"成功删除消息{message_id}！")
    else:
        logger.info(f"删除最新的消息{message_id}！")

def generate_filename(file_name, file_size, caption, file_getpath):
    # 生成新的文件名
    file_extension = os.path.splitext(file_name)[1] or os.path.splitext(file_getpath)[1]
    file_size_str = f"({format_size(file_size)})"
    new_file_name = file_name

    if all(char in string.ascii_letters + string.digits + string.punctuation for char in file_name):
        if caption:
            new_file_name = caption[:40]
        else:
            new_file_name = os.path.splitext(file_name)[0]  # 去除原始文件名的后缀

    else:
        new_file_name = os.path.splitext(file_name)[0]  # 去除原始文件名的后缀


    new_file_name = f"{new_file_name}{file_size_str}{file_extension}"
    return new_file_name    

def download_file(url, file_type, file_name, caption, file_getpath, message_id, chat_id, media_group_id, file_size):
       
    total_size = file_size

    file_name_with_size = generate_filename(file_name, total_size, caption, file_getpath)
    logger.info(f"【{media_group_id}】文件{file_name}重命名为：{file_name_with_size}")

    if media_group_id:
        if caption:
            caption_path = caption[:40]
            file_type = f"media_group/{caption_path}【{media_group_id}】"
        else:
            file_type = f"media_group/【{media_group_id}】"

    sub_directory = os.path.join(download_path, file_type)
    create_directory(sub_directory)

    file_path = os.path.join(sub_directory, file_name_with_size)

    os.link(file_getpath, file_path) 
    logger.info(f"【{media_group_id}】{file_getpath},{file_path}")
    
    if enable_upload:
        # 构造远程路径
        remote_file_path = f"{remote_path}/{file_type}"
            
        # 调用rclone命令上传文件，此处rclone逻辑与rclone_upload(local_path, remote_path, second_dir)函数不相同，不可修改
        # 引用路径以处理空格和特殊字符
        quoted_file_path = shlex.quote(file_path)
        quoted_remote_file_path = shlex.quote(remote_file_path)

        logger.info(f"rclone本地地址:{quoted_file_path}")
        logger.info(f"rclone远程地址:{quoted_remote_file_path}")
            
        rclone_command = f"rclone move {quoted_file_path} {quoted_remote_file_path} -P"
        result = subprocess.run(rclone_command, shell=True)
        
        time_sleep = 600 # 删除回复信息时间
        link_url = remote_url + "/" + file_type + "/" + file_name_with_size
        if media_group_id:
            link_url = remote_url + "/" + file_type
            if media_group_id in media_group_id_end_count:
                media_group_id_end_count[media_group_id] += 1
            else:
                media_group_id_end_count[media_group_id] = 1

            media_group_id_start_time = media_group_id_start_count[media_group_id] #总共次数
            media_group_id_end_time = media_group_id_end_count[media_group_id] #已经出现次数
            logging.info(f"【{media_group_id}】总共 {media_group_id_start_time} 已上传完成{media_group_id_end_time}")
            
            if media_group_id_start_time == media_group_id_end_time:
                logging.info(f"【{media_group_id}】{media_group_id_end_time}个文件全部上传完成")
                reply_text = f"【{media_group_id}】{media_group_id_end_time}个文件全部上传完成\n\n<a href='{link_url}'>文件链接</a>"
                send_reply(chat_id, message_id, reply_text, time_sleep, link_url)   
        else:
            if result.returncode == 0:
                logging.info("【{media_group_id}】文件 {file_name_with_size} 上传完成")
                reply_text = f"【{media_group_id}】文件 {file_name_with_size} 上传完成\n\n<a href='{link_url}'>文件链接</a>"
                send_reply(chat_id, message_id, reply_text, time_sleep, link_url)
            else:
                logging.error(f"【{media_group_id}】文件 {file_name_with_size} 上传失败，返回码：{result.returncode}")
                reply_text = f"【{media_group_id}】文件 {file_name_with_size} 上传失败，返回码：{result.returncode}"
                send_reply(chat_id, message_id, reply_text, time_sleep, link_url)
    else:
        # 未开启rclone上传
        reply_text = f"一个文件 {file_name_with_size} 上传完成\n\n<a href='{link_url}'>文件链接</a>"
        send_reply(chat_id, message_id, reply_text, time_sleep, '123123')

def download_media_file(file_id, file_name, file_type, caption, message_id, chat_id, media_group_id):
    get_file_url = f"{api_base_url}{bot_token}/getFile"
    params = {"file_id": file_id}

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(get_file_url, params=params, timeout=30)  # timeout可调整
            logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}尝试获取 file_info: {response}")

            file_info = response.json()
            logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}file_info: {file_info}")

            if file_info.get("ok") and "result" in file_info:
                file_path = file_info["result"]["file_path"]
                file_size = file_info["result"].get("file_size", 0)
                file_url = f"{api_base_url}{bot_token}/{file_path}"

                download_file(file_url, file_type, file_name, caption, file_path, message_id, chat_id, media_group_id, file_size)
                return  # 成功获取并下载后退出函数
            else:
                logger.warning(f"【{media_group_id} | {file_id}】\n{' ' * 26}获取文件信息失败，返回值: {file_info}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"【{media_group_id} | {file_id}】\n{' ' * 26}server端telegram-bot-api还未将tg云端文件下载到本地。\n{' ' * 26}本次请求异常: {e}")

        retries += 1
        logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}等待 {retry_delay}s 后重试第 {retries} 次...")
        time.sleep(retry_delay)

    logger.error(f"【{media_group_id} | {file_id}】\n{' ' * 26}多次请求server端telegram-bot-api，重试后仍未获取 file_info: {file_id}，不再尝试")

def download_ytdlp_file(url, message_id, chat_id):
    logger.info(f"开始下载：{url}")

    ## 获取网站类型，后续cookies文件名
    ## ytdlp的cookies文件，Netscape格式
    cmd = f"yt-dlp --print extractor {url}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    logger.info(f"result:{result}")
    
    s = str(result)
    m = re.search(r"stdout='(.*?)\\n", s) 

    if m:
        extractor = m.group(1)
        print(extractor)    # BiliBili
    
    logger.info(f"网站判断：{url} ==> {extractor}")
    cookies = f"./cookies/{extractor}.txt"
    a = create_empty_file(cookies)
    
    logger.info(f"网站{extractor}如需使用cookies下载，请将Netscape格式cookies添加到{cookies}，错误cookies会导致下载失败")
    
    # 配置 yt-dlp
    file_second = 'ytdlp'
    download_path_tg = os.path.join(download_path, file_second)
    create_directory(download_path_tg)
    logger.info(f"{url}下载到目录：{download_path_tg}")

    if a != True:
        ## 存在cookies文件，调用cookies,错误会导致下载失败
        ## --no-playlist \
        cmd = f"""yt-dlp \
        --no-playlist \
        --format 'bv+ba' \
        --output "{download_path_tg}/%(title)s_%(resolution)s_%(id)s.%(ext)s" \
        --retries 10 \
        --fragment-retries 10 \
        --concurrent-fragments 5 \
        --cookies {cookies} \
        --no-overwrites \
        --print after_move:filepath \
        {url}"""
    else:
        ## 不存在cookies文件，不使用cookies下载
        cmd = f"""yt-dlp \
        --no-playlist \
        --format 'bv+ba' \
        --output "{download_path_tg}/%(title)s_%(resolution)s_%(id)s.%(ext)s" \
        --retries 10 \
        --fragment-retries 10 \
        --concurrent-fragments 5 \
        --no-overwrites \
        --print after_move:filepath \
        {url}"""

        logger.info(f"删除空白文件{cookies}")
        os.remove(cookies)

    try:
        # 捕获输出，避免阻塞
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True) #
        if result.returncode == 0:

            downloaded_file = result.stdout.strip().split("\n")[-1]

            if not downloaded_file:
                downloaded_file = download_path_tg
            
            # 后续是否移动文件
            if enable_upload != True:
                logger.info(f"ytdlp下载成功：{url} ==> {download_path_tg}")
                reply_text = f"ytdlp下载成功：{url} ==> {download_path_tg}"
                send_reply(chat_id, message_id, reply_text, time_sleep, '123')
                return

            rclone_upload(downloaded_file, remote_path, file_second, message_id, chat_id)
            
        else:
            logger.error(f"ytdlp下载失败：{url}")
            reply_text = f"ytdlp下载失败：{result.stderr}"
            send_reply(chat_id, message_id, reply_text, time_sleep, '123')
    except Exception as e:
        logger.error(f"执行命令异常：{e}")
        reply_text = f"执行命令异常：{e}"
        send_reply(chat_id, message_id, reply_text, time_sleep, '123')


def rclone_upload(local_path, remote_path, second_dir, message_id, chat_id):

    remote_file_path = f"{remote_path}/{second_dir}"
    quoted_file_path = shlex.quote(local_path)
    quoted_remote_file_path = shlex.quote(remote_file_path)
    
    rclone_command = f"rclone move {quoted_file_path} {quoted_remote_file_path} -P"
    result = subprocess.run(rclone_command, shell=True)
    
    if result.returncode == 0:
        logger.info(f"rclone上传成功：{quoted_file_path} ==> {quoted_remote_file_path}")
        reply_text = f"rclone上传成功：{quoted_file_path} ==> {quoted_remote_file_path}"
        send_reply(chat_id, message_id, reply_text, time_sleep, '123')
        return True
    else:
        logger.error(f"rclone上传失败：{quoted_file_path} ==> {quoted_remote_file_path} | ，返回码：{result.returncode}")
        reply_text = f"rclone上传失败：{quoted_file_path} ==> {quoted_remote_file_path} | ，返回码：{result.returncode}"
        send_reply(chat_id, message_id, reply_text, time_sleep, '123')
        return False

def process_message(message, media_group_captions, caption, media_group_id):
    message_id = message['message_id']
    chat_id = message['chat']['id']

    # 将caption传递给同一media_group_id的其他文件
    if media_group_id and media_group_id in media_group_captions:
        caption = media_group_captions[media_group_id]
    
    # 检查用户是否在允许的用户ID列表中
    if chat_id not in allowed_user_ids:
        logger.info(f"未经授权的用户：{chat_id}")
        return

    if "photo" in message:
        # 处理照片
        photo = message["photo"][-1]  # 获取最后一张照片（原始分辨率）
        file_id = photo["file_id"]
        file_name = photo.get("file_name", "photo")
        logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}收到照片消息，开始下载：{file_name}")
        # download_media_file(file_id, file_name, "photos",caption, message_id, chat_id, media_group_id)
        pool.submit(download_media_file, file_id, file_name, "photos", caption, message_id, chat_id, media_group_id)

    if "document" in message:
        # 处理文档
        document = message["document"]
        file_id = document["file_id"]
        file_name = document.get("file_name", "document")
        logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}收到文档消息，开始下载：{file_name}")
        # download_media_file(file_id, file_name, "documents",caption, message_id, chat_id, media_group_id)
        pool.submit(download_media_file, file_id, file_name, "documents", caption, message_id, chat_id, media_group_id)

    if "video" in message:
        # 处理视频
        video = message["video"]
        file_id = video["file_id"]
        file_name = video.get("file_name", "video")
        logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}收到视频消息，开始下载：{file_name}")
        #download_media_file(file_id, file_name, "videos",caption, message_id, chat_id, media_group_id)
        #thread = threading.Thread(target=download_media_file, args=(file_id, file_name, "videos", caption, message_id, chat_id, media_group_id))
        #thread.start()
        
        # 提交任务给线程池后台执行
        pool.submit(download_media_file, file_id, file_name, "videos", caption, message_id, chat_id, media_group_id) 

    if "audio" in message:
        # 处理音频
        audio = message["audio"]
        file_id = audio["file_id"]
        file_name = audio.get("file_name", "audio")
        logger.info(f"【{media_group_id} | {file_id}】\n{' ' * 26}收到音频消息，开始下载：{file_name}")
        # download_media_file(file_id, file_name, "audios",caption, message_id, chat_id, media_group_id)
        pool.submit(download_media_file, file_id, file_name, "audios", caption, message_id, chat_id, media_group_id)

    if "text" in message:
        # 处理文本文件
        text = message["text"]
        #if (text.startswith("/ping") or text.startswith("/start")) and len(text) == 5:
        if (text.startswith("/ping") and len(text) == 5) or (text.startswith("/start") and len(text) == 6) or (text.startswith("/ping@")):
        #if text.startswith("/ping") and len(text) == 5:
            # 如果消息以 /ping 开头，回复 Pong! 🏓
            time_sleep = 2
            send_reply(chat_id, message_id, "Pong! 🏓", time_sleep, link_url)

            #删除回复的消息
            thread = threading.Thread(target=delete_latest_message, args=(chat_id, message_id, time_sleep))
            thread.start()

        ## 使用yt-dlp下载youtube等网站视频，请先安装ffmpeg与ytdlp
        if text.startswith("/ytdlp"):
            if not ytdlp:
                return
            parts = text.split()
            if len(parts) != 2:
                logger.info("请使用：/ytdlp <url>")
                reply_text = "请使用：/ytdlp+空格+链接"
                time_sleep = 5
                send_reply(chat_id, message_id, reply_text, time_sleep , '123')

                #删除回复的消息
                thread = threading.Thread(target=delete_latest_message, args=(chat_id, message_id, time_sleep))
                thread.start()

                return

            logger.info("收到ytdlp内容，开始下载...") 
            url = parts[1]
            pool.submit(download_ytdlp_file, url, message_id, chat_id)

def get_updates(offset=None):
    get_updates_url = f"{api_base_url}{bot_token}/getUpdates"
    params = {"offset": offset}

    response = requests.get(get_updates_url, params=params)
    updates = response.json()

    if updates["ok"]:
        return updates["result"]
    else:
        return []

def cleanup_media_group_captions(media_group_captions, media_group_timestamps):
    current_time = time.time()
    # 遍历字典中的所有项
    for media_group_id, timestamp in list(media_group_timestamps.items()):
        # 检查时间戳是否超过清理间隔
        if current_time - timestamp > cleanup_interval:
            # 删除旧数据
            del media_group_captions[media_group_id]
            del media_group_timestamps[media_group_id]

def get_captions(media_group_id, last_update_id1, media_group_captions, media_group_timestamps):   
    new_updates = get_updates(offset=last_update_id1)
    if new_updates:
        logger.info(f"调用请求caption函数，last_update_id1：[{last_update_id1}]")
        logger.info(f"调用请求caption函数，updates：[{new_updates}]")
        for update in new_updates:
            if "message" in update:
                new_message = update["message"]
                new_media_group_id = new_message.get("media_group_id")
                caption = new_message.get("caption")
                logger.info(f"调用函数,{last_update_id1} ，新new_message{new_message}，新new_media_group_id{new_media_group_id}，新captain{caption}")
                
                if new_media_group_id == media_group_id:
                    if caption:
                        caption = re.sub(r'\n+', ' ', caption) #处理避免换行符
                        logger.info(f"调用函数,media_group_id {media_group_id} 存在caption {caption}") 
                        get_media_group_captions(caption, media_group_id, media_group_captions, media_group_timestamps)  
                        return caption
                    else:
                        logger.info(f"调用函数，未获取到captain ，last_update_id {last_update_id1} 继续获取caption")
                else:
                    logger.info(f"退出调用函数，后续为media_group_id不同部分，原来{media_group_id} 、新的{new_media_group_id}！！！") 
                    return 

def get_media_group_captions(caption, media_group_id, media_group_captions, media_group_timestamps):
    if caption and media_group_id:
        if media_group_id not in media_group_captions:
            media_group_captions[media_group_id] = caption  # 存储 caption
            media_group_timestamps[media_group_id] = time.time()  # 存储时间戳
            logger.info(f"存储有效captain media_group_id字典对。captain：[{caption}]；media_group_id：[{media_group_id}]")
        else:
            # 更新时间戳
            media_group_timestamps[media_group_id] = time.time()

        # 清理旧数据
        cleanup_media_group_captions(media_group_captions, media_group_timestamps) 
                             
def main():
    last_update_id = None
    media_group_captions = {}  # media_group_captions 字典初始化为空
    
    # 定义存储时间戳的字典
    media_group_timestamps = {}
    

    while True:
        updates = get_updates(offset=last_update_id)

        if updates:
            #logger.info(f"if updates: {updates}")
            #从单次更新的所有消息中获取caption
            logger.info(f"从获取的所有消息中获取caption")
            for update in updates:
                if "message" in update:
                    message = update["message"]
                    caption = message.get("caption")
                    media_group_id = message.get("media_group_id")

                    if caption:
                        caption = re.sub(r'\n+', ' ', caption) #处理避免换行符

                    get_media_group_captions(caption, media_group_id, media_group_captions, media_group_timestamps)
            logger.info(f"开始for循环，逐一处理获取的所有消息...")
            for update in updates:
                #logger.info(f"for update in updates：{update}")
                if "message" in update:
                    message = update["message"]
                    logger.info(f"循环中，当前处理的消息，update_id:[{last_update_id}]，message:[{message}]")
                    
                    media_group_id = message.get("media_group_id")
                    caption = message.get("caption")
                    if caption:
                        caption = re.sub(r'\n+', ' ', caption) #处理避免换行符
                    if media_group_id:
                        if media_group_id in media_group_id_start_count:
                            media_group_id_start_count[media_group_id] += 1
                        else:
                            media_group_id_start_count[media_group_id] = 1

                    # 若media_group_id不为空，从字典查看是否有caption
                    if media_group_id and media_group_id in media_group_captions:
                        caption = media_group_captions[media_group_id]

                    # 从字典查看没有caption，又存在media_group_id，重新请求下一轮tg消息，获取caption
                    if media_group_id and not caption:
                        last_update_id1 = update["update_id"] + 1
                        #用下一个last_update_id，重新请求tg消息
                        caption = get_captions(media_group_id, last_update_id1, media_group_captions, media_group_timestamps)
                        if caption:
                            caption = re.sub(r'\n+', ' ', caption) #处理避免换行符
                            logger.info(f"请求下一个update_id {last_update_id1}以后的所有消息，发现media_group_id [{media_group_id}] 存在caption [{caption}]") 
                        else:
                            logger.info(f"请求下一个update_id {last_update_id1}以后的所有消息，发现media_group_id [{media_group_id}] 不存在caption ！！！")                
                    
                    process_message(message, media_group_captions, caption, media_group_id)
                     
                last_update_id = update["update_id"] + 1

if __name__ == "__main__":
    create_directory(download_path)
    main()

