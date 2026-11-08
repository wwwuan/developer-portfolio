from flask import Blueprint,request,jsonify,g
from exts import db,r
from jwt_utils import jwt_required
import os
import tempfile
import zipfile
import shutil
from werkzeug.utils import secure_filename
import logging
from models import ProjectModel,ImageResultModel
import uuid
from config import target_path, MAX_RUNNING
from .fileprocessor import AsyncFileProcessor
import json


"""
压缩包的解压
文件的上传和下载
3.6修改内容：将文件上传部分拉出来单独一个进程
可优化部分：把redis改为aioresdis，从同步存储变成异步，优化性能
"""

logger = logging.getLogger(__name__)

bp=Blueprint('photo_transfer',__name__,url_prefix='/photo_transfer')



def process_zip_file(zip_path,project_id,path):
    #处理ZIP文件内容
    result = {
        #创造一个字典，存入后续返回给客户端的数据
        'zip_file': os.path.basename(path),
        'total_files': 0,
        'extracted_files': 0,
        'failed_files': [],
        'path':path,
        'file_list': []
    }
    try:#插入文件具体实现
        zip_check(zip_path)
        # 打开ZIP文件
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 获取ZIP文件列表
            file_list = zip_ref.namelist()
            print("文件列表获取成功")
            result['total_files'] = len(file_list)
            path = result['path']

            #启动redis处理
            afp = AsyncFileProcessor()
            afp.start_async_processing(project_id, file_list)

            """ 
            解压所有文件，一个个图片放入redis处理
            """
            for filename in file_list:
                try:
                    # 跳过目录
                    if filename.endswith('/'):
                        continue

                    # 创建目标路径
                    target_path_tmp = os.path.join(path, filename)
                    os.makedirs(os.path.dirname(target_path_tmp), exist_ok=True)

                    # 提取文件
                    with zip_ref.open(filename) as source, open(target_path_tmp, 'wb') as target:
                        shutil.copyfileobj(source, target)

                    image=ImageResultModel(
                        project_id=project_id,
                        image_filename=filename,
                        image_path=target_path_tmp
                    )
                    db.session.add(image)
                    db.session.commit()

                    #将图片地址放入redis
                    upload_redis(image)

                    result['extracted_files'] += 1
                    result['file_list'].append({
                        'filename': filename,
                        'size': os.path.getsize(target_path_tmp),
                        'path': target_path_tmp
                    })

                except Exception as e:
                    result['failed_files'].append({
                        'filename': filename,
                        'error': str(e)
                    })

    except zipfile.BadZipFile as e:
        project = ProjectModel.query.filter_by(project_id=project_id).first()
        if not project:
            raise ValueError(f"项目不存在：{project_id}")
        project.status = 'error'
        db.session.commit()
        raise Exception(f"ZIP文件损坏或格式不正确: {str(e)}")

    return result

def zip_check(zip_path):
    try:  # 检验文件是否可读，目标文件夹是否可写入
        # 1. 首先验证ZIP文件是否存在且可读
        if not os.path.exists(zip_path):
            raise Exception(f"ZIP文件不存在: {zip_path}")

        if not os.access(zip_path, os.R_OK):
            raise Exception(f"没有读取ZIP文件的权限: {zip_path}")

        #print(f"目标目录绝对路径: {target_path}")  # 调试信息

        # 3. 验证目标目录
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)
            #print(f"创建目标目录: {target_path}")

        if not os.access(target_path, os.W_OK):
            raise Exception(f"没有写入目标目录的权限: {target_path}")

        #print("所有验证通过，准备打开ZIP文件")

    except Exception as e:
        raise Exception(f"预检查出错: {e}")

    return "ok"

def upload_redis(image):
    """将对象image放入redis"""
    try:
        """
        思路：在用户正在处理图片不超过最大同时处理数时放入image_task_list由worker提取
        超过最大处理数放入user_id:{g.user_id}:waiting_image_list由另一函数遍历
        """
        data={
            'user_id':g.user_id,
            'image_id':image.id
        }
        count=int(r.get(f"user_id:{g.user_id}:count") or 0)
        print("count:",count)
        if count > MAX_RUNNING or count < 0:
            r.set(f"user_id:{g.user_id}:count",0)
        count=int(r.get(f"user_id:{g.user_id}:count") or 0)
        if count<MAX_RUNNING:
            r.incr(f"user_id:{g.user_id}:count")
            r.lpush("image_task_list",json.dumps(data))
        else:
            r.lpush(f"user_id:{g.user_id}:waiting_image_list",json.dumps(data))
    except Exception as e:
        print(f"error:{str(e)}")
        raise e

    return '正在处理中，请稍候'


@bp.route('/upload-zip', methods=['POST'])
@jwt_required
def handle_zip_upload():
    """处理ZIP文件上传和解压路由"""
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({
                'status':'error',
                'message': '未上传文件'
            }), 400

        file = request.files['file']

        # 检查文件名是否有效
        if file.filename == '':
            return jsonify({
                'status':'error',
                'message': '未选择文件'
            }), 400

        # 验证文件类型
        if not file.filename.lower().endswith('.zip'):
            return jsonify({
                'status':'error',
                'message': '只支持ZIP格式文件'
            }), 400

        # 创建临时目录处理ZIP文件
        with tempfile.TemporaryDirectory() as temp_dir:
            # 安全保存上传的ZIP文件
            zip_filename = secure_filename(file.filename)#将用户文件名转化为安全文件名，防止恶意入侵
            zip_path = os.path.join(temp_dir, zip_filename)
            file.save(zip_path)
            """
            temp_dir
                zip_path -- file
            """

            # 将数据放入数据库的操作
            project_id = uuid.uuid4().hex
            user_id = g.user_id
            path = os.path.join(target_path, project_id)
            total_files = 0
            project = ProjectModel(
                project_id=project_id,
                user_id=user_id,
                username=g.current_user.username,
                zip_filename=zip_filename,
                original_zip_filename=file.filename,
                path=path,
                total_files=total_files
            )
            db.session.add(project)
            db.session.commit()

            # 解压并处理文件
            result = process_zip_file(zip_path,project_id,path)

            # 返回处理结果
            return jsonify({
                'success': True,
                'project_id': project_id,
                'message': 'ZIP文件处理完成',
                'data': result
            })

    except Exception as e:
        logger.error(f"处理ZIP文件时出错: {str(e)}")
        return jsonify({'error': f'处理失败: {str(e)}'}), 500

@bp.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'healthy', 'service': 'zip-processor'})
