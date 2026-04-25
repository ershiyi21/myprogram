#!/bin/sh

if [ -z "$(ls -A /var/www/html)" ]; then
    echo "文件夹为空"
    cp  /opt/default/index.php /var/www/html/index.php
    cp  /opt/default/files.js /var/www/html/files.js
    cp -r /opt/default/_files/ /var/www/html/_files/
fi

chown -R www-data:www-data /var/www

# 启动 Apache
exec "$@"
