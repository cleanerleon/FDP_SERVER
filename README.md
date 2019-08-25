基于FATE 0.3平台开发的数据平台，数据版咸鱼

- fdp 
    - 封装了FATE平台上传文件、获取交集大小、Hetero LR评估、训练、预测函数
    - Node.py声明了可以进行FATE操作的类

- server
    - 基于flask实现web service和cli接口
    - func.py: 基础函数，web service和cli为对其的调用
    - main.py: web service
    - cli.py: cli，执行格式为python cli.py xxx
    - model：ORM
    
- wxapp
    - 微信小程序
    
命令行demo
- python cli.py show_users

- python cli.py show_models

- python cli.py topup 1 100

- python cli.py auto_train 1 'model auto trained on 1'

- python cli.py predict 1 1 3

- python cli.py show_trans

- python cli.py show_data
