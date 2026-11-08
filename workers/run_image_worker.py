from pathlib import Path
import sys

# Make the project root importable when this file is launched directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from workers.worker import ImageAnalysisWorker
import threading
import logging
import signal
import time

app = create_app()
logger = logging.getLogger(__name__)

def run_worker():
    """启动工作线程"""
    try:
        worker = ImageAnalysisWorker(app=app)
        worker.start()
    except Exception as e:
        logger.error(f"工作线程异常: {e}")
    finally:
        logger.info("工作线程结束")

def signal_handler(signum, frame):
    """处理关闭信号"""
    logger.info(f"收到信号: {signum}，正在退出...")
    sys.exit(0)

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 启动工作线程
worker_thread = threading.Thread(
    target=run_worker,
    daemon=False,
    name="ImageAnalysisWorker"
)
worker_thread.start()

logger.info("✅ 图片分析后台 worker 已启动")

# 主线程保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("收到 Ctrl+C，正在停止...")
    # 等待工作线程结束
    if worker_thread.is_alive():
        worker_thread.join(timeout=5)
    logger.info("Worker 已停止")
