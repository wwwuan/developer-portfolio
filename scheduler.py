from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from models import UserModel, ProjectModel
import logging

logger = logging.getLogger(__name__)


def init_scheduler(app):
    """初始化并启动定时任务"""
    scheduler = BackgroundScheduler()

    # 每天凌晨2点执行用户数据清理
    @scheduler.scheduled_job('cron', hour=2, minute=0)
    def cleanup_expired_users():
        with app.app_context():
            try:
                deleted_count = UserModel.cleanup_expired_users()
                logger.info(f"自动清理了 {deleted_count} 个过期用户")
            except Exception as e:
                logger.error(f"清理过期用户时出错: {str(e)}")

    # 可以添加其他定时任务，比如项目数据清理
    @scheduler.scheduled_job('cron', hour=3, minute=0)
    def cleanup_expired_projects():
        with app.app_context():
            try:
                # 假设ProjectModel也有类似的清理方法
                deleted_count = ProjectModel.cleanup_expired_projects()
                logger.info(f"自动清理了 {deleted_count} 个过期项目")
            except Exception as e:
                logger.error(f"清理过期项目时出错: {str(e)}")

    scheduler.start()

    # 注册关闭钩子
    atexit.register(lambda: scheduler.shutdown())

    return scheduler