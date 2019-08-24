# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, KFold

from fdp.file_mgr import upload_csv, list_tables, list_models, del_table, del_model, start_proc
from fdp.hetero_lr import cv, train, predict
from fdp.fl_intersect import get_cross_size


class Node:
    # nid从1开始，0被我用做平台的id了
    def __init__(self, nid):
        self.nid = nid

    # 上传文件到平台
    # path：本地路径，当前仅支持csv，默认label栏是第一列
    # table_name: 平台的文件名，如存在将会覆盖
    def upload(self, path, table_name):
        start_proc(upload_csv, self.nid, path, table_name)

    # 查看本人在平台保存的数据文件
    def browse_tables(self):
        return list_tables(self.nid)

    # 查看别人在平台保存的数据文件
    # nid：别人的nid
    def browse_other_tables(self, nid):
        return list_tables(nid)

    # 查看本人在平台保存的训练好的模型
    def browse_models(self):
        return list_models(self.nid)

    # 删除本人在平台保存的数据文件
    def del_table(self, table_name):
        start_proc(del_table, self.nid, table_name)

    # 删除本人在平台保存的模型
    def del_model(self, model_name):
        start_proc(del_model, self.nid, model_name)

    # 查看本人的数据集和别人的数据集的交集大小
    def get_cross_size(self, guest_table, host_nid, host_table):
        gpid = 10000
        hpid = 9999
        return get_cross_size(gpid, self.nid, guest_table, hpid, host_nid, host_table)

    # 查看本人的数据集和别人的数据集进行联邦学习训练逻辑回归的交叉验证的AUC分数
    # gy_id guest table y id
    # hy_id host table y id
    def get_hetero_lr_score(self, my_table, gy_id, other_nid, other_table, hy_id):
        cv_score = cv(self.nid, my_table, gy_id, other_nid, other_table, hy_id)
        return np.mean(cv_score['auc'])

    # 仅使用本地数据训练逻辑回归模型的交叉验证的分数
    # path：本地csv文件
    # id_col：id栏
    # label_col: 标签栏
    @staticmethod
    def get_local_lr_score(path, id_col, label_col):
        df = pd.read_csv(path)
        lr = LogisticRegression(solver='lbfgs')
        X = df.drop([id_col, label_col], axis=1)
        y = df[label_col]
        scores = cross_val_score(lr, X, y, cv=5, scoring='roc_auc', n_jobs=-1)
        return scores.mean()

    # 使用联邦学习训练逻辑回归模型并保存到model_name
    def hetero_lr_train(self, guest_table, gy_id,host_id, host_table, hy_id, model_name):
        train(self.nid, guest_table, gy_id, host_id, host_table, hy_id, model_name)

    # 使用训练好的模型预测，返回dataframe，格式为 id，label，prob
    def hetero_lr_predict(self, my_table, gy_id, other_nid, other_table, hy_id, model_name):
        return predict(self.nid, my_table, gy_id, other_nid, other_table, hy_id, model_name)


if __name__ == '__main__':
    guest_file = r'data/guest_demo.csv'
    host_a_file = r'data/host_demo_a.csv'
    host_b_file = r'data/host_demo_b.csv'
    guest_table = r'guest_table'
    host_a_table = r'host_a_table'
    host_b_table = r'host_b_table'
    guest_id = 1
    host_a_id = 2
    host_b_id = 3

    guest_node = Node(guest_id)
    host_a_node = Node(host_a_id)
    host_b_node = Node(host_b_id)

    # for node in (guest_node, host_a_node, host_b_node):
    #     for table_name in guest_node.browse_tables():
    #         guest_node.del_table(table_name)

    guest_node.upload(guest_file, guest_table)
    print('guest node files:')
    print(guest_node.browse_tables())

    score = guest_node.get_local_lr_score(guest_file, 'id', 'y')
    print('local training score:', score)

    for title, nid, file, table in (('host a', host_a_id, host_a_file, host_a_table),
                              ('host b', host_b_id, host_b_file, host_b_table)):
        host_node = Node(nid)
        host_node.upload(file, table)
        print(title+' node files:')
        print(host_node.browse_tables())

        print('get intersection size...')
        size = guest_node.get_cross_size(guest_table, nid, table)
        print(title + ' intersection size:', size)

        print('get f1 score...')
        score = guest_node.get_hetero_lr_score(guest_table, 0, nid, table, -1)
        print(title + ' fl score:', score)

        print('train...')
        model_name = title + ' model'
        guest_node.hetero_lr_train(guest_table, 0, nid, table, -1, model_name)
        print('guest models:')
        print(guest_node.browse_models())

        print('predict...')
        pred_df = guest_node.hetero_lr_predict(guest_table, 0, nid, table, -1, model_name)
        print(pred_df.head())

    print('guest node files:')
    print(guest_node.browse_tables())
