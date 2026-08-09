#!/bin/bash

LOG_MAIN="/var/log/signage_start.log"
LOG_ERR="/var/log/signage_start_error.log"

DATE=$(date +"%Y-%m-%d")

# ローテーション
if [ -f "$LOG_MAIN" ]; then
    mv "$LOG_MAIN" "/var/log/signage_start_$DATE.log"
fi

if [ -f "$LOG_ERR" ]; then
    mv "$LOG_ERR" "/var/log/signage_start_error_$DATE.log"
fi

# 新しいログファイルを作成
touch "$LOG_MAIN"
touch "$LOG_ERR"

# 権限を戻す
chmod 644 "$LOG_MAIN"
chmod 644 "$LOG_ERR"
