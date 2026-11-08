import logging
from exts import db,r
from models import ProjectModel
import json
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

class AsyncFileProcessor:
    def __init__(self):
        self.redis = r

    def start_async_processing(self, project_id, file_list):
        """启动异步文件处理"""
        try:
            # 初始化Redis计数
            redis_key = f"project:{project_id}:processing"
            self.redis.hset(redis_key, 'total_files', len(file_list))
            self.redis.hset(redis_key, 'processed_files', 0)
            self.redis.hset(redis_key, 'error_files', 0)
            self.redis.hset(redis_key, 'error_details', json.dumps([]))
            self.redis.hset(redis_key, 'start_time', datetime.now(timezone.utc).isoformat())
            print(file_list)

            # 更新项目状态为处理中
            project = ProjectModel.query.filter_by(project_id=project_id).first()
            project.status = 'processing'
            project.started_at = datetime.now(timezone.utc).isoformat()
            project.error_message = json.dumps({
                'progress': 0,
                'message': '异步处理中...'
            })
            db.session.commit()

            return True, "异步处理已启动"

        except Exception as e:
            logger.error(f"启动异步处理失败: {str(e)}")
            return False, str(e)

    def update_processing_result(self, project_id, filename, status, error_msg=None):
        """更新单个文件的处理结果到Redis"""
        redis_key = f"project:{project_id}:processing"

        print(f"status:{status}")

        try:
            if status == 'completed':
                # 成功计数
                self.redis.hincrby(redis_key, 'processed_files', 1)
            else:
                # 失败计数和记录错误信息
                self.redis.hincrby(redis_key, 'error_files', 1)

                # 获取现有错误列表
                error_details_json = self.redis.hget(redis_key, 'error_details')
                error_details = json.loads(error_details_json) if error_details_json else []

                # 添加新错误
                error_details.append({
                    'filename': filename,
                    'error': error_msg,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                self.redis.hset(redis_key, 'error_details', json.dumps(error_details))

            # 更新进度
            total_files = int(self.redis.hget(redis_key, 'total_files'))
            processed_count = int(self.redis.hget(redis_key, 'processed_files') or 0)
            error_count = int(self.redis.hget(redis_key, 'error_files') or 0)
            progress = (processed_count + error_count) / total_files * 100

            self.redis.hset(redis_key, 'progress', progress)

            # 检查是否所有文件都处理完成
            print(f"processed_count:{processed_count},error_count:{error_count}")
            if processed_count + error_count >= total_files:
                print(f"redy_project_id:{project_id}")
                self.finalize_project_status(project_id)

            return True

        except Exception as e:
            logger.error(f"更新处理结果失败: {str(e)}")
            return False

    def finalize_project_status(self, project_id):
        """所有文件处理完成后，更新数据库状态"""
        print(f"project_id:{project_id}")
        try:
            print("更新数据库状态")
            redis_key = f"project:{project_id}:processing"

            # 从Redis获取最终结果
            total_files = int(self.redis.hget(redis_key, 'total_files'))
            processed_files = int(self.redis.hget(redis_key, 'processed_files') or 0)
            processed_count = int(self.redis.hget(redis_key, 'processed_files') or 0)
            error_count = int(self.redis.hget(redis_key, 'error_files') or 0)
            error_files = int(self.redis.hget(redis_key, 'error_files') or 0)
            error_details_json = self.redis.hget(redis_key, 'error_details')
            error_details = json.loads(error_details_json) if error_details_json else []

            # 更新项目表
            project = ProjectModel.query.filter_by(project_id=project_id).first()
            project.total_files = total_files
            project.processed_files = processed_files
            project.error_files = error_files
            project.completed_at = datetime.now(timezone.utc).isoformat()
            project.success_count=processed_count
            project.error_count=error_count

            if error_files > 0:
                project.status = 'failed'
                project.error_message = json.dumps({
                    'total_files': total_files,
                    'success_files': processed_files,
                    'failed_files': error_files,
                    'error_files': [e['filename'] for e in error_details],
                    'error_details': error_details,
                    'completion_time': datetime.now(timezone.utc).isoformat()
                }, ensure_ascii=False)
            else:
                project.status = 'completed'
                project.error_message = None

            db.session.commit()

            # 清理Redis数据（可选）
            self.redis.delete(redis_key)

            logger.info(f"项目 {project_id} 处理完成，成功: {processed_files}, 失败: {error_files}")

        except Exception as e:
            logger.error(f"最终化项目状态失败: {str(e)}")
            # 可以设置重试机制

    async def view_analysis_progress(self, project_id, status):
        """异步获取分析进度（Python3.11适配：同步Redis操作放入线程池）"""

        # 定义同步Redis查询函数（避免阻塞异步事件循环）
        def sync_get_progress():
            try:
                redis_key = f"project:{project_id}:processing"
                total_files = int(self.redis.hget(redis_key, 'total_files') or 0)
                processed_count = int(self.redis.hget(redis_key, 'processed_files') or 0)
                error_count = int(self.redis.hget(redis_key, 'error_files') or 0)
                progress_result = {'status': status, 'total_files': total_files, 'processed_files': processed_count,
                                   'error_files': error_count}
            except Exception as e:
                # 捕获Redis操作异常，避免单个项目报错影响整体
                logger.error(f"获取项目 {project_id} 分析进度失败：{str(e)}", exc_info=True)
                progress_result = {'status': 'error', 'total_files': 0, 'processed_files': 0, 'error_files': 0}
            return progress_result

        # Python3.11 异步执行同步Redis操作（避免阻塞事件循环）
        result = await asyncio.get_event_loop().run_in_executor(None, sync_get_progress, ())
        return result