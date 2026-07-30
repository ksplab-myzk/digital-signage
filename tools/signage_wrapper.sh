#!/bin/bash

SIGNAGE="/Users/yourname/signage/signage.py"
LOCKFILE="/Users/yourname/signage/signage.lock"
LOGFILE="/Users/yourname/signage/logs/signage.log"
ERRFILE="/Users/yourname/signage/logs/error.log"

MAIL_TO="yourmail@example.com"

echo "$(date) - Starting signage" >> "$LOGFILE"

# ロックファイルが残っていたら削除（安全）
if [ -f "$LOCKFILE" ]; then
    echo "$(date) - Lockfile found. Removing stale lockfile." >> "$LOGFILE"
    rm -f "$LOCKFILE"
fi

# サイネージ実行
/usr/bin/python3 "$SIGNAGE"
EXIT_CODE=$?

# 異常終了時の処理
if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date) - Crash detected (exit code: $EXIT_CODE)" >> "$ERRFILE"

    # ロックファイルが残っていたら削除
    if [ -f "$LOCKFILE" ]; then
        echo "$(date) - Removing lockfile after crash." >> "$ERRFILE"
        rm -f "$LOCKFILE"
    fi

    # メール通知
    echo "サイネージがクラッシュしました（exit code: $EXIT_CODE）" \
        | mail -s "Signage Crash" "$MAIL_TO"
fi

# LaunchAgent の KeepAlive が再起動するので終了
exit 0
