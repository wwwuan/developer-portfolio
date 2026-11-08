import logging
from exts import db,r
from models import ImageResultModel
import base64
import requests
from config import api_endpoint, max_analysis_time, MAX_RUNNING
from blueprints.file_processing.fileprocessor import AsyncFileProcessor
from concurrent.futures import ThreadPoolExecutor
import json
import time

logger = logging.getLogger(__name__)

"""
可优化部分，减少数据库的连接，把图片信息先写入redis再统一存储
"""

# workers/image_worker.py
class ImageAnalysisWorker:
    def __init__(self,app,max_workers=1000):
        self.redis = r
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.app=app
        self.max_analysis_time = max_analysis_time

    def start(self):
        """启动worker（独立进程）"""
        while self.running:
            task_data = self.redis.brpop('image_task_list', timeout=10)
            if task_data:
                print("获取到任务")
                self.executor.submit(self._process_task, task_data)

    def process_single_task(self, task_data):
        """处理单个图片分析任务的限时处理"""
        with self.app.app_context():
            # 使用 `submit` 提交任务，并通过 `future.result(timeout)` 设置超时
            future = self.executor.submit(self._process_task, task_data)
            try:
                # 设置最大超时时间，如果超时则抛出 TimeoutError
                future.result(timeout=self.max_analysis_time)  # 最大执行时间
            except TimeoutError:
                print(f"任务超时: {task_data}")
                # 处理超时的任务，可以更新任务状态为失败
                _, data_byte = task_data
                data = json.loads(data_byte.decode())
                image_id = int(data['image_id'])
                image = ImageResultModel.query.filter_by(id=image_id).first()
                image.status = 'failed'
                image.error_message = '诊断超时'
                db.session.add(image)
                return
            except Exception as e:
                # 捕获其他所有异常
                print(f"任务处理出现异常: {e}")
                return

    def _process_task(self, task_data):
        """处理单个图片分析任务"""
        start_time = time.time()
        with self.app.app_context():
            try:
                _, data_byte = task_data
                data = json.loads(data_byte.decode())
                user_id = int(data['user_id'])
                image_id = int(data['image_id'])
                image = ImageResultModel.query.filter_by(id=image_id).first()
                print(f"开始处理{image.image_filename}")
                with open(image.image_path, 'rb') as f:
                    image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                payload = {
                    'image': image_base64,
                    'model': 'clip'  # 或其他分析模型
                }
                response = requests.post(
                    api_endpoint,
                    json=payload,
                    timeout=self.max_analysis_time
                )
                if response.status_code == 200:
                    image.status = 'completed'
                    # 存储API返回的JSON数据
                    image.analysis_result = response.json()  # 提取JSON内容
                else:
                    image.status = 'failed'
                    image.error_message = f"分析错误: {response.status_code} - {response.text}"
                print("图片分析完成")

            except requests.Timeout:
                logger.warning(
                    "Image analysis request timed out after %.2fs (limit %.2fs)",
                    time.time() - start_time,
                    self.max_analysis_time
                )
                image.status = 'failed'
                image.error_message = '分析超时'
            except Exception as e:
                # 处理失败的任务
                image.status = 'failed'
                image.error_message = str(e)

            finally:
                elapsed = time.time() - start_time
                # 超时判断
                if elapsed >= self.max_analysis_time and image.status != 'failed':
                    print(f"任务超时: {image.image_filename}")
                    image.status = 'failed'
                    image.error_message = "任务超时"

                logger.info(
                    "Image task %s finished with status=%s in %.2fs (limit %.2fs)",
                    image.id,
                    image.status,
                    elapsed,
                    self.max_analysis_time
                )

                print("调用更新单个文件处理结果函数")

                project_id = image.project_id
                filename = image.image_filename
                status = image.status
                error_msg = image.error_message

                db.session.commit()

                print(project_id, filename, error_msg)

                afp = AsyncFileProcessor()
                afp.update_processing_result(project_id, filename, status, error_msg)

                print("处理等待池事务进入处理池")
                self.redis.decr(f"user_id:{user_id}:count")
                waiting_data_byte = self.redis.rpop(f"user_id:{user_id}:waiting_image_list")
                if waiting_data_byte is None:
                    return
                waiting_data=json.loads(waiting_data_byte.decode())
                print("waiting_data",waiting_data,type(waiting_data))
                count=int(self.redis.get(f"user_id:{user_id}:count"))
                print("active_count",count)
                if waiting_data:
                    if count >= MAX_RUNNING:
                        self.redis.lpush(f"user_id:{user_id}:waiting_image_list", json.dumps(waiting_data))
                        return
                    print("从等待队列取出")
                    print("等待处理队列",self.redis.llen("image_task_list"))
                    try:
                        self.redis.lpush("image_task_list",json.dumps(waiting_data))
                    except Exception as e:
                        print(str(e))
                    self.redis.incr(f"user_id:{user_id}:count")
                    print(self.redis.get("user_id:{user_id}:count"))
