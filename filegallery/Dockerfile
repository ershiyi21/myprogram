FROM php:8.2-apache

# ✅ 1. 编译环境 + 依赖（关键修复点）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    autoconf \
    pkg-config \
    re2c \
    libonig-dev \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# ✅ 2. GD
RUN docker-php-ext-configure gd --with-freetype --with-jpeg \
 && docker-php-ext-install gd

# ✅ 3. mbstring
RUN docker-php-ext-install mbstring

# ✅ 4. exif
RUN docker-php-ext-install exif

# Apache
RUN a2enmod rewrite

# 创建默认文件目录
RUN mkdir -p /opt/default

COPY index.php /opt/default/index.php
COPY files.js /opt/default/files.js
COPY _files/ /opt/default/_files/
RUN chown -R www-data:www-data /var/www
RUN chown -R www-data:www-data /opt/default

# 启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["apache2-foreground"]

EXPOSE 8080
