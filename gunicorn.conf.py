 # 并行工作进程数
workers = 4
# 指定每个工作者的线程数
threads = 2
 # 端口 5000
bind = '0.0.0.0:5000'
# 设置守护进程,将进程交给supervisor管理
daemon = 'false'
# 工作模式协程
worker_class = 'gevent'
# 设置最大并发量
worker_connections = 2000
