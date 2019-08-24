import concurrent
import multiprocessing
import os
from decimal import Decimal

import pandas as pd
import hashlib
from flask_script import Manager

from fdp.Node import Node
from fdp.fl_intersect import get_cross_size
from server import app, db
from server.func import func_train, func_auto_train, func_topup, func_show_hosts, \
    func_show_table, func_get_tables, func_get_target_tables, func_predict, func_show_trans, func_show_data, \
    func_add_table_name, func_update_table
from server.helper import db_commit, Params, RetVal, TransType
from server.model.SizeResult import SizeResult
from server.model.Table import Table
from server.model.TableName import TableName
from server.model.Transaction import Transaction
from server.model.User import User

manager = Manager(app)


@manager.command
def create_db():
    db.create_all()


@manager.command
def drop_db():
    db.drop_all()


@manager.command
def add_ds(guid, name):
    guid = int(guid)
    func_add_table_name(guid, name)


@manager.command
def update_table(tnid, path, id_col, y_col, memo):
    tnid = int(tnid)
    if not os.path.exists(path):
        return
    func_update_table(tnid, path, id_col, y_col, memo)


# show_users
@manager.command
def show_users():
    users = User.query.order_by(User.id).all()
    for user in users:
        print('用户ID: %d,\t用户名: %s,\t余额: %.2f' % (user.id, user.name, user.balance))
        for table_name in user.table_names:
            print('\t数据源ID: %d,\t名称: %s' % (table_name.id, table_name.name))
            for table in table_name.tables:
                print('\t\t表格ID: %d,\t版本: %d,\t时间: %s,\t备注: \"%s\"' % (table.id, table.ver, table.time, table.memo))
                print('\t\t\t定价训练价格: %.2f,\t竞价训练价格: %.2f,\t预测价格: %.2f' \
                      % (table.price0, table.price1, table.price2))
                print('\n')

# predict mid gtid
@manager.command
def show_models():
    users = User.query.order_by(User.id).all()
    for user in users:
        print('USER ID: %d,\tname: %s' % (user.id, user.name))
        for model_name in user.model_names:
            print('\tMODEL ID: %d,\tname: %s' % (model_name.id, model_name.name))
            for model in model_name.models:
                print('\t\tMODEL ID: %d,\tver: %d,\tcreate time: %s,\tmemo: %s' % (model.id, model.ver, model.time, model.memo))
        print('\n')

# topup uid amount
@manager.command
def topup(uid, amount):
    uid = int(uid)
    amount = float(amount)
    func_topup(uid, amount)
    user = User.query.get(uid)
    print('USER %d balance %.2f' % (uid, user.balance))

# train gtid htid memo
@manager.command
def train(gtid, htid, memo):
    gtid = int(gtid)
    htid = int(htid)
    guest_table = Table.query.get(gtid)
    guid = guest_table.name.uid
    host_table = Table.query.get(htid)
    func_train(guid, guest_table, host_table, memo)

# auto_train gtid memo
@manager.command
def auto_train(gtid, memo):
    gtid = int(gtid)
    guest_table = Table.query.get(gtid)
    guid = guest_table.name.uid
    func_auto_train(guid, guest_table, memo)

# predict mid gtid
@manager.command
def predict(mid, gtid, htid):
    gtid = int(gtid)
    mid = int(mid)
    htid = int(htid)
    guest_table = Table.query.get(gtid)
    host_table = Table.query.get(htid)
    func_predict(mid, guest_table, host_table)

# show_trans
@manager.command
def show_trans(guid):
    guid = int(guid)
    func_show_trans(guid)


# show_data
@manager.command
def show_data():
    func_show_data()


if __name__ == '__main__':
    manager.run()