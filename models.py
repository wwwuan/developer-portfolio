"""
表格形式
"""
from exts import db,utc_to_local
from datetime import datetime, timezone, timedelta

class UserModel(db.Model):#定义表
    __tablename__ = 'users'#表名
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    username = db.Column(db.String(100),nullable=False,unique=True)
    password = db.Column(db.String(200),nullable=False)
    email = db.Column(db.String(100),nullable=False)
    status = db.Column(db.String(100),nullable=False,default="active")#deleted
    password_version = db.Column(db.Integer,nullable=False,default=1)#密码版本，实现修改密码后token失效
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 新增软删除字段
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.Integer)  # 删除者ID（管理员ID）
    deletion_reason = db.Column(db.Text)  # 删除原因
    scheduled_purge = db.Column(db.DateTime)  # 计划永久删除时间

    @classmethod
    def get_active_users(cls):
        """获取未删除的用户"""
        return cls.query.filter_by(is_deleted=False)

    @classmethod
    def get_deleted_users(cls):
        """获取已删除的用户"""
        return cls.query.filter_by(is_deleted=True)

    def soft_delete(self, deleter_id, reason=None, purge_days=30):
        """
        软删除用户
        :param deleter_id: 执行删除的管理员ID
        :param reason: 删除原因
        :param purge_days: 保留天数（默认30天）
        """
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleter_id
        self.deletion_reason = reason
        self.scheduled_purge = datetime.now(timezone.utc) + timedelta(days=purge_days)

        projects=ProjectModel.query.filter_by(id=self.id).all()
        for project in projects:
            ProjectModel.query.soft_delete(project)

        # 同时标记用户状态为禁用
        self.status = "deleted"

        db.session.commit()

    def restore(self):
        """恢复已删除的用户"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None
        self.scheduled_purge = None
        self.status = "active"  # 恢复为活跃状态

        projects = ProjectModel.query.filter_by(id=self.id).all()
        for project in projects:
            ProjectModel.query.restore(project)

        db.session.commit()

    @classmethod
    def cleanup_expired_users(cls):
        """清理过期的已删除用户"""
        expired_users = cls.query.filter(
            cls.is_deleted == True,
            cls.scheduled_purge <= datetime.now(timezone.utc)
        ).all()

        for user in expired_users:
            # 先删除用户相关的项目数据
            user_projects = ProjectModel.query.filter_by(user_id=user.id).all()
            for project in user_projects:
                # 删除项目包含的文件
                images=ImageResultModel.query.filter_by(project_id=project.id).all()
                for image in images:
                    db.session.delete(image)
                db.session.delete(project)

            # 然后删除用户
            db.session.delete(user)

        db.session.commit()
        return len(expired_users)


class AdminUserModel(db.Model):#定义表
    __tablename__ = 'admin_users'#表名
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    username = db.Column(db.String(100),nullable=False,unique=True)
    password = db.Column(db.String(200),nullable=False)
    email = db.Column(db.String(100),nullable=False)
    status = db.Column(db.String(100),nullable=False,default="active")
    password_version = db.Column(db.Integer,nullable=False,default=1)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    update_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)


class ProjectModel(db.Model):
    """
    项目主表 - 合并等待和已完成的项目
    """
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    project_id = db.Column(db.String(40), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    zip_filename = db.Column(db.String(200), nullable=False)  # 压缩包文件名
    original_zip_filename = db.Column(db.String(200))  # 原始文件名
    path = db.Column(db.String(200), nullable=False)
    total_files = db.Column(db.Integer, nullable=False, default=0)

    upload_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    success_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default='waiting')
    # waiting, uploading, processing, completed, failed(在诊断时失败），error（其他部分失败，显示上传失败）

    result_path = db.Column(db.String(200))  # 总体结果文件路径
    started_at = db.Column(db.DateTime)  # 开始处理时间
    completed_at = db.Column(db.DateTime)  # 完成时间
    error_message = db.Column(db.Text)  # 错误信息,存放错误文件文件名

    # 软删除相关字段
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.Integer)  # 删除者ID
    deletion_type = db.Column(db.String(20))  # 'user' 或 'admin'
    scheduled_purge = db.Column(db.DateTime)  # 计划清理时间

    @property
    def deleted(self):
        """获取软删除状态"""
        return self.is_deleted

    @deleted.setter
    def deleted(self, value):
        """设置软删除状态"""
        self.is_deleted = value


    """查询方法"""
    @staticmethod
    def get_projects_base_query(filters=None, order_by=None, desc=True):
        """基础查询方法"""
        query = ProjectModel.query

        # 应用过滤条件
        if filters:
            if isinstance(filters, dict):
                query = query.filter_by(**filters)
            else:
                query = query.filter(filters)

        # 应用排序
        if order_by is None:
            order_by = ProjectModel.upload_time

        query = query.filter_by(is_deleted=False)

        order = order_by.desc() if desc else order_by.asc()
        query = query.order_by(order)

        return query

    @staticmethod
    def paginate_query(query, page=1, per_page=10, error_out=False):
        """统一分页方法"""
        return query.paginate(
            page=page,
            per_page=per_page,
            error_out=error_out
        )

    @staticmethod
    def get_projects_with_pagination(user_id, page=1, per_page=10, desc=True):
        """分页查询指定用户的项目"""
        query = ProjectModel.get_projects_base_query(
            filters={'user_id': user_id},
            desc=desc
        )
        return ProjectModel.paginate_query(query, page, per_page)

    """删除与恢复方法"""
    @classmethod
    def get_deleted_projects(cls):
        """获取已删除的项目"""
        return cls.query.filter_by(is_deleted=True)

    def soft_delete(self, deleter_id, is_admin=False):
        """
        统一软删除方法
        :param deleter_id: 执行删除的用户ID
        :param is_admin: 是否是管理员操作
        """
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleter_id
        self.deletion_type = 'admin' if is_admin else 'user'

        # 设置自动清理时间（管理员90天，用户30天）
        retention_days = 90 if is_admin else 30
        self.scheduled_purge = datetime.now(timezone.utc) + timedelta(days=retention_days)

        db.session.commit()

    def restore(self):
        """恢复软删除的项目"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_type = None
        self.scheduled_purge = None
        db.session.commit()

    @classmethod
    def cleanup_expired_projects(cls):
        """清理过期的已删除项目"""
        expired_projects = cls.query.filter(
            cls.is_deleted == True,
            cls.scheduled_purge <= datetime.now(timezone.utc)
        ).all()

        for project in expired_projects:

            # 删除项目包含的文件
            images=ImageResultModel.query.filter_by(project_id=project.id).all()
            for image in images:
                db.session.delete(image)
            db.session.delete(project)

        db.session.commit()
        return len(expired_projects)

class ProcessingProject(ProjectModel):
    __tablename__ = 'processing_projects'

    def move_to_project(self):
        """ 将处理中的项目迁移到ProjectModel """
        project = ProjectModel(
            project_id=self.project_id,
            user_id=self.user_id,
            username=self.username,
            zip_filename=self.zip_filename,
            original_zip_filename=self.original_zip_filename,
            path=self.path,
            total_files=self.total_files,
            upload_time=self.upload_time,
            success_count=self.success_count,
            error_count=self.error_count,
            status='completed',  # 状态改为已完成
            result_path=self.result_path,
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc),
            error_message=self.error_message
        )
        db.session.add(project)
        db.session.delete(self)
        db.session.commit()
        return project

class ImageResultModel(db.Model):
    """
    单张图片分析结果表
    """
    __tablename__ = 'image_results'

    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    project_id = db.Column(db.String(40), db.ForeignKey('projects.project_id'), nullable=False)
    image_filename = db.Column(db.String(200), nullable=False)  # 图片文件名
    image_path = db.Column(db.String(200), nullable=False)  # 图片完整路径

    status = db.Column(db.String(20), nullable=False, default='waiting')  # waiting, processing, completed, failed
    analysis_result = db.Column(db.JSON)  # 分析结果（JSON格式）
    error_message = db.Column(db.Text)  # 错误信息

    analyzed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 索引优化查询
    __table_args__ = (
        db.Index('idx_project_image', 'project_id', 'image_filename'),
        db.Index('idx_project_status', 'project_id', 'status'),
    )


class ProjectSummaryView:
    """项目汇总视图（虚拟表，用于查询）"""

    @staticmethod
    def get_project_summary(project_id):
        """获取项目汇总信息"""
        # 获取项目基本信息
        project = ProjectModel.query.filter_by(project_id=project_id,is_deleted=False).first()
        if not project:
            return None

        # 统计总信息
        return {
            'username': project.username,
            'project_id': project.project_id,
            'project_name': project.original_zip_filename,
            'total_images': project.total_files,
            'success_count': project.success_count,
            'error_count': project.error_count,
            'status': project.status,
            'upload_time': utc_to_local(project.upload_time),
            'completed_at': utc_to_local(project.completed_at),
            'completion_rate': round(
                (project.success_count + project.error_count) / project.total_files * 100, 2
            ) if project.total_files > 0 else 0
        }

def cleanup_expired():
    """ 清理已软删除并过期的项目 """
    ProjectModel.cleanup_expired_projects()
    ProcessingProject.cleanup_expired_projects()
    ImageResultModel.cleanup_expired_projects()
