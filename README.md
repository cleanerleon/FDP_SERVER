基于FATE 0.3平台开发的数据平台，数据版咸鱼

fdp 
封装了FATE平台获取交集大小、Hetero LR评估、训练、预测函数
具体查看Node.py

server
基于flask实现web service和cli接口
main.py: web service
cli.py: cli
func.py: 基础函数，web service和cli为对其的调用
model：ORM
