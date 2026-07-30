import psutil
import time
import datetime
import platform

# ログファイル（1日単位）
def get_log_path():
    today = datetime.date.today().strftime("%Y-%m-%d")
    return f"memlog_{today}.txt"

def log(msg):
    with open(get_log_path(), "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] {msg}\n")
    print(msg)

def get_process_info(name):
    procs = []
    for p in psutil.process_iter(attrs=['pid', 'name']):
        if p.info['name'] == name:
            procs.append(psutil.Process(p.info['pid']))
    return procs

def log_process_memory(proc, label):
    try:
        mem = proc.memory_info()
        rss = mem.rss                 # WorkingSet (物理メモリ)
        vms = mem.vms                 # Virtual Bytes (仮想メモリ)
        pf = getattr(mem, 'pfaults', None)

        # Private Bytes（Windowsは PrivateMemorySize、macOSは vms が近似）
        if platform.system() == "Windows":
            private = proc.memory_info().private
        else:
            private = mem.vms  # macOSは private が取れないため近似

        log(f"{label} PID={proc.pid} "
            f"RSS={rss/1024/1024:.2f}MB "
            f"Private={private/1024/1024:.2f}MB "
            f"Virtual={vms/1024/1024:.2f}MB")
    except Exception as e:
        log(f"{label} PID={proc.pid} error: {e}")

def main():
    log("=== メモリ監視開始 ===")

    while True:
        # python.exe / python3
        py_name = "python.exe" if platform.system() == "Windows" else "python3"
        py_procs = get_process_info(py_name)

        for proc in py_procs:
            log_process_memory(proc, "Python")

        # QtWebEngineProcess
        qt_name = "QtWebEngineProcess.exe" if platform.system() == "Windows" else "QtWebEngineProcess"
        qt_procs = get_process_info(qt_name)

        for proc in qt_procs:
            log_process_memory(proc, "QtWebEngine")

        log("---")

        time.sleep(60)  # 1分ごと

if __name__ == "__main__":
    main()
