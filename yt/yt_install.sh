#!/bin/bash

# ===============================================
# 首次安装 yt 快捷命令脚本
# 安装 /usr/local/bin/yt，用于后续更新 yt-dlp
# ===============================================

YT_BIN="/usr/local/bin/yt"
YTDLP_BIN="/usr/local/bin/yt-dlp"

# 检查是否已经安装 yt
if [ -f "$YT_BIN" ]; then
    echo "yt 快捷命令已存在：$YT_BIN"
    echo "可直接使用 'yt' 命令更新 yt-dlp 或下载视频"
    exit 0
fi

# 判断系统架构
OS=$(uname -s)
ARCH=$(uname -m)

# 选择对应的 yt-dlp nightly URL
URL=""
if [[ "$OS" == "Linux" ]]; then
    if [[ "$ARCH" == "x86_64" ]]; then
        URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp_linux"
    elif [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
        URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp_linux_arm64"
    else
        echo "未识别的 Linux 架构: $ARCH"
        exit 1
    fi
elif [[ "$OS" == "Darwin" ]]; then
    URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp_macos"
else
    echo "当前系统不支持自动安装 yt-dlp: $OS"
    exit 1
fi

# 下载 yt-dlp
echo "正在安装 yt-dlp..."
sudo curl -L -o "$YTDLP_BIN" "$URL"
sudo chmod +x "$YTDLP_BIN"

echo "yt-dlp 安装完成，版本信息："
yt-dlp --version

# 创建 yt 快捷命令
echo "正在创建 yt 快捷命令..."
cat << 'EOF' | sudo tee "$YT_BIN" > /dev/null
#!/bin/bash
# 快捷命令 yt：更新 yt-dlp 或下载视频
# 如果直接运行 yt，无参数则提示更新
if [ $# -eq 0 ]; then
    read -p "是否更新 yt-dlp 到最新 nightly？ (y/n) " choice
    case "$choice" in
        y|Y )
            ARCH=$(uname -m)
            URL=""
            OS=$(uname -s)
            if [[ "$OS" == "Linux" ]]; then
                if [[ "$ARCH" == "x86_64" ]]; then
                    URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp_linux"
                elif [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
                    URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp_linux_arm64"
                fi
            elif [[ "$OS" == "Darwin" ]]; then
                URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp_macos"
            fi
            sudo curl -L -o /usr/local/bin/yt-dlp "$URL"
            sudo chmod +x /usr/local/bin/yt-dlp
            echo "yt-dlp 已更新，版本信息："
            yt-dlp --version
            ;;
        * )
            echo "取消更新。"
            exit 0
            ;;
    esac
else
    # 如果有参数，则直接当作 yt-dlp 命令
    yt-dlp "$@"
fi
EOF

sudo chmod +x "$YT_BIN"
echo "安装完成！后续可以直接使用 'yt' 命令更新yt-dlp。"
