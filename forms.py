import wtforms
from wtforms.validators import Email,Length,EqualTo
from config import ADMIN_WHITELIST
from models import UserModel,AdminUserModel
from exts import r


#验证前端提交的数据是否符合要求
class LoginForm(wtforms.Form):
    email = wtforms.StringField('Email', validators=[Email(message="邮箱格式错误"), ])
    password = wtforms.StringField('password', validators=[Length(min=6, max=20, message="密码格式错误")])


class RegisterForm(wtforms.Form):
    email=wtforms.StringField('Email',validators=[Email(message="邮箱格式错误"),])
    captcha=wtforms.StringField('captcha',validators=[Length(min=4,max=4,message="验证码格式错误")])
    username=wtforms.StringField('username',validators=[Length(min=1,max=20,message="用户名格式错误")])
    password=wtforms.StringField('password',validators=[Length(min=6,max=20,message="密码格式错误")])
    password_confirm=wtforms.StringField('password_confirm',validators=[EqualTo("password",message="两次密码不一致")])

    #自定义验证
    #1.邮箱是否被注册
    def validate_email(self,field):
        if self.email.errors:
            return
        if field.errors:
            return

        email=field.data
        if UserModel.query.filter_by(email=email,status="active").first():
            raise wtforms.ValidationError(message="该邮箱已被注册")

    #2.验证码是否正确
    def validate_captcha(self,field):
        if self.email.errors:
            return
        captcha=field.data
        #print(captcha)
        email=self.email.data
        get_captcha=r.get(email)
        print(get_captcha)
        if get_captcha is None:
            raise wtforms.ValidationError(message="验证码已过期或不存在")
        get_captcha=get_captcha.decode()
        if get_captcha != captcha:
            raise wtforms.ValidationError(message="邮箱或验证码错误")
        r.delete(email)

    def validate_username(self,field):
        if self.captcha.errors:
            return
        username=field.data
        print("username",username)
        if UserModel.query.filter_by(username=username).first():
            raise wtforms.ValidationError(message="该用户名已存在")

class AdminRegisterForm(wtforms.Form):
    email=wtforms.StringField('Email',validators=[Email(message="邮箱格式错误"),])
    captcha=wtforms.StringField('captcha',validators=[Length(min=4,max=4,message="验证码格式错误")])
    username=wtforms.StringField('username',validators=[Length(min=1,max=20,message="用户名格式错误")])
    password=wtforms.StringField('password',validators=[Length(min=6,max=20,message="密码格式错误")])
    password_confirm=wtforms.StringField('password_confirm',validators=[EqualTo("password",message="两次密码不一致")])

    #自定义验证
    #1.邮箱是否被注册
    def validate_email(self,field):
        email=field.data
        if email not in ADMIN_WHITELIST:
            raise wtforms.ValidationError(message="无管理员注册资格")
        if AdminUserModel.query.filter_by(email=email,status="active").first():
            raise wtforms.ValidationError(message="该邮箱已被注册")

    #2.验证码是否正确
    def validate_captcha(self,field):
        captcha=field.data
        email=self.email.data
        get_captcha=r.get(email)
        print(get_captcha)
        if get_captcha is None:
            raise wtforms.ValidationError(message="验证码已过期或不存在")
        get_captcha=get_captcha.decode()
        if get_captcha != captcha:
            raise wtforms.ValidationError(message="邮箱或验证码错误")
        r.delete(email)

#忘记密码
class ResetPasswordForm(wtforms.Form):
    email = wtforms.StringField('email', validators=[Email(message="邮箱格式错误"), ])
    captcha = wtforms.StringField('captcha', validators=[Length(min=4, max=4, message="验证码格式错误")])
    new_password = wtforms.StringField('new_password', validators=[Length(min=6, max=20, message="密码格式错误")])
    new_password_confirm = wtforms.StringField('new_password_confirm',validators=[
        EqualTo("new_password", message="两次密码不一致")
    ])

    # 验证码是否正确
    def validate_captcha(self, field):
        if self.email.errors:
            return

        if field.errors:
            return

        captcha = field.data
        email = self.email.data
        get_captcha = r.get(email)
        print(get_captcha)
        if get_captcha is None:
            raise wtforms.ValidationError(message="验证码已过期或不存在")
        get_captcha = get_captcha.decode()
        if get_captcha != captcha:
            raise wtforms.ValidationError(message="邮箱或验证码错误")
        r.delete(email)
        return


class ChangePasswordForm(wtforms.Form):
    old_password = wtforms.StringField('old_password', validators=[Length(min=6, max=20, message="旧密码格式错误")])
    new_password = wtforms.StringField('new_password', validators=[Length(min=6, max=20, message="新密码格式错误")])
    new_password_confirm = wtforms.StringField('new_password_confirm',
                                               validators=[EqualTo("new_password", message="两次密码不一致")])

