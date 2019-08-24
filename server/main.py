# -*- coding: utf-8 -*-

import datetime
import os
import uuid

from flask import request, session, render_template, url_for, redirect
import json
import hashlib
import pandas as pd

from server.func import func_get_target_tables, func_show_hosts, func_get_tables, func_show_table
from server.helper import RetVal, Params, Logger, db_commit, get_param, get_uid, get_params, get_table_param, \
    TransType

from server.model.Table import Table
from server.model.TableName import TableName
from server.model.Transaction import Transaction
from server.model.User import User
from server import app, db
from fdp.Node import Node

MAX_ROW = 1000
MAX_COLUMN = 25


@app.route('/')
def index_page():
    return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    username = get_param(Params.NAME)
    password = get_param(Params.PASSWORD)
    print(username, password)
    resp_json = {}
    if username is None or password is None:
        resp_json[Params.RESULT] = RetVal.LACK_PARAM.value
        return json.dumps(resp_json)
    pw_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
    user = User.query.filter_by(name=username, pw_hash=pw_hash).first()
    if user is None:
        resp_json[Params.RESULT] = RetVal.NO_RECORD.value
        return json.dumps(resp_json)
    token = uuid.uuid1().hex + hashlib.md5(str(datetime.datetime.now()).encode('utf-8')).hexdigest()
    resp_json[Params.RESULT] = RetVal.OK.value
    resp_json[Params.TOKEN] = token
    session[Params.UID] = user.id
    session[Params.NAME] = user.name
    session[Params.TOKEN] = token
    return json.dumps(resp_json)


@app.route('/user_page', methods=['GET', 'POST'])
def user_page():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return redirect(url_for('index_page'))
    user = User.query.get(uid)
    guest_table_names = user.table_names
    print(uid)
    hosts = User.query.filter(User.id!=uid).all()
    print(hosts)
    return render_template('user.html', user=user,
                           guest_table_names=guest_table_names,
                           hosts=hosts)
# /add_table
# param:token, file, name, id_col, label_col, memo
# gid：自己表格的id，返回本地学习交叉验证的分数
# 耗时API
# return:result,score
@app.route('/add_table', methods=['GET', 'POST'])
def add_table():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    name, id_col, label_col, memo = get_params((Params.NAME, Params.ID_COL, Params.LABEL_COL, Params.MEMO))
    if name is None or 'file' not in request.files:
        resp_json[Params.RESULT] = RetVal.LACK_PARAM.value
        return json.dumps(resp_json)

    # save table name
    tn_rec = TableName()
    tn_rec.uid = uid
    tn_rec.name = name
    db.session.add(tn_rec)
    resp_json = db_commit()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)

    # save table record to get name
    t_rec = Table()
    t_rec.name_id = tn_rec.id
    t_rec.memo = memo
    t_rec.id_col = id_col
    t_rec.y_col = label_col
    db.session.add(t_rec)
    resp_json = db_commit()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        db.session.delete(tn_rec)
        db_commit()
        return json.dumps(resp_json)

    # check csv file
    local_path = t_rec.get_local_path()
    file = request.files['file']
    file.save(local_path)
    try:
        df = pd.read_csv(local_path)
        resp_json[Params.RESULT] = RetVal.OK.value
    except Exception as e:
        os.unlink(local_path)
        logger = Logger.get_logger()
        logger.error('upload_file exception: %s', str(e))
        resp_json[Params.RESULT] = RetVal.FILE_INV.value
        df = None

    if df is not None:
        r, c = df.shape
        if r <= MAX_ROW and c <= MAX_COLUMN and id_col in df.columns:
            if label_col in df.columns:
                label_id = df.drop(id_col, axis=1).columns.get_loc(label_col)
            elif len(label_col) == 0:
                label_id = -1
            else:
                label_id = None
                resp_json[Params.RESULT] = RetVal.FILE_INV.value
            if label_id is not None:
                t_rec.y_col_id = label_id
                node = Node(uid)
                fate_path = t_rec.get_fate_path()
                node.upload(local_path, fate_path)
                resp_json = db_commit()
                if resp_json[Params.RESULT] == RetVal.OK:
                    return json.dumps(resp_json)
        else:
            resp_json[Params.RESULT] = RetVal.FILE_LARGE.value

    db.session.delete(tn_rec)
    db.session.delete(t_rec)
    db_commit()
    os.unlink(local_path)
    return json.dumps(resp_json)


# /update_table
# param:token, file, nid, id_col, label_col, memo
# gid：自己表格的id，返回本地学习交叉验证的分数
# 耗时API
# return:result,score
@app.route('/update_table', methods=['GET', 'POST'])
def update_table():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    nid, id_col, label_col, memo = get_params((Params.NID, Params.ID_COL, Params.LABEL_COL, Params.MEMO))
    if nid is None or 'file' not in request.files:
        resp_json[Params.RESULT] = RetVal.LACK_PARAM.value
        return json.dumps(resp_json)

    # save table record to get name
    t_rec = Table.query.filter_by(name_id=nid).order_by(Table.ver.desc()).first()
    if t_rec is Node:
        resp_json[Params.RESULT] = RetVal.NO_RECORD.value
        return json.dumps(resp_json)
    ver = t_rec.ver
    t_rec = Table()
    t_rec.name_id = nid
    t_rec.memo = memo
    t_rec.id_col = id_col
    t_rec.y_col = label_col
    t_rec.ver = ver + 1

    db.session.add(t_rec)
    resp_json = db_commit()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)

    # check csv file
    local_path = t_rec.get_local_path()
    file = request.files['file']
    file.save(local_path)
    try:
        df = pd.read_csv(local_path)
        resp_json[Params.RESULT] = RetVal.OK.value
    except Exception as e:
        os.unlink(local_path)
        logger = Logger.get_logger()
        logger.error('upload_file exception: %s', str(e))
        resp_json[Params.RESULT] = RetVal.FILE_INV.value
        df = None

    if df is not None:
        r, c = df.shape
        if r <= MAX_ROW and c <= MAX_COLUMN and id_col in df.columns:
            if label_col in df.columns:
                label_id = df.drop(id_col, axis=1).columns.get_loc(label_col)
            elif len(label_col) == 0:
                label_id = -1
            else:
                label_id = None
                resp_json[Params.RESULT] = RetVal.FILE_INV.value
            if label_id is not None:
                t_rec.y_col_id = label_id
                node = Node(uid)
                fate_path = t_rec.get_fate_path()
                node.upload(local_path, fate_path)
                resp_json = db_commit()
                if resp_json[Params.RESULT] == RetVal.OK:
                    return json.dumps(resp_json)
        else:
            resp_json[Params.RESULT] = RetVal.FILE_LARGE.value

    db.session.delete(t_rec)
    db_commit()
    os.unlink(local_path)
    return json.dumps(resp_json)


# param:token
# 返回已上传的表格信息列表，表格信息包括id，表格名，上传时间和备注
# return:result,tables[(nid, name, table(gid,ver,time,memo,price0,price1,price2,score))]
@app.route('/get_tables', methods=['GET', 'POST'])
def get_tables():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    return json.dumps(func_get_tables(uid))


# param:toke, id
# mid：表格id，返回表格内容
# return：result, table[(head...),(data...)...]
@app.route('/show_table', methods=['GET', 'POST'])
def show_table():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    resp_json, gid = get_param(Params.ID)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    return json.dumps(func_show_table(uid, gid))

#
# # /get_models
# # param:token
# # 返回已上传的模型信息列表，模型信息包括id，模型名，上传时间和备注
# # return:result,[(model_name,time,memo)]
# @app.route('/get_models')
# def get_models():
#     resp_json = {}
#     ret, uid = get_uid()
#     if ret != RetVal.OK:
#         resp_json[Params.RESULT] = ret
#         return json.dumps(resp_json)
#     models = Model.query.filter_by(uid=uid).order_by(Table.ver.desc()).all()
#     resp_json[Params.TABLES] = [{Params.ID:model.id,
#                                  Params.NAME: model.name,
#                                  Params.VER: model.ver,
#                                  Params.MEMO: model.memo} for model in models]
#     resp_json[Params.RESULT] = RetVal.OK
#     return json.dumps(resp_json)
#
# /get_hosts
# 返回其他节点id
# return：result, users[(id, name)]
@app.route('/get_hosts', methods=['GET', 'POST'])
def get_hosts():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    return json.dumps(func_show_hosts(uid))

# /get_host_tables
# param：token，id
# 返回其他节点的表格
# return:result,[(id,table_name,time,memo)]
@app.route('/get_host_tables', methods=['GET', 'POST'])
def get_host_tables():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    resp_json, hid = get_param(Params.ID)
    if hid is None:
        return json.dumps(resp_json)

# /get_fixed_price_tables
# param：token，gtid
# 返回其他节点的表格
# return:result, tables[id]
@app.route('/get_fixed_price_tables', methods=['GET', 'POST'])
def get_fixed_price_tables():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    resp_json. guest_table = get_table_param(Params.GTID)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)
    return func_get_target_tables(uid, guest_table, TransType.TRAIN.value)

# # /get_cross_size
# # param:token, gid, hid
# # gid：自己表格的id，hid：别人表格的id，返回两个表格的交集
# # 耗时API
# # return:result,size
# @app.route('/get_cross_size')
# def get_cross_size():
#     resp_json = {}
#     ret, uid = get_uid()
#     if ret != RetVal.OK:
#         resp_json[Params.RESULT] = ret
#         return json.dumps(resp_json)
#     hid = get_param(Params.HID)
#     gid = get_param(Params.GID)
#     if hid is None or gid is None:
#         resp_json[Params.RESULT] = RetVal.LACK_PARAM
#         return json.dumps(resp_json)
#     cross_size = CrossSize.query.filter_by(hid=hid, gid=gid).first()
#     if cross_size is not None:
#         resp_json[Params.RESULT] = RetVal.OK
#         resp_json[Params.SIZE] = cross_size.size
#         return json.dumps(resp_json)
#     host_table = Table.query.get(hid)
#     guest_table = Table.query.get(gid)
#     if host_table is None or guest_table is None:
#         resp_json[Params.RESULT] = RetVal.NO_RECORD
#         return json.dumps(resp_json)
#     host_fate_path = host_table.get_fate_path()
#     guest_fate_path = guest_table.get_fate_path()
#     node = Node(uid)
#     size = node.get_cross_size(guest_fate_path, host_table.uid, host_fate_path)
#     cross_size = CrossSize()
#     cross_size.hid = hid
#     cross_size.gid = gid
#     cross_size.size = size
#     db.session.add(cross_size)
#     ret = db_commit()
#     resp_json[Params.RESULT] = ret
#     resp_json[Params.SIZE] = size
#     return json.dumps(resp_json)
#
# # /hetero_lr_cv
# # param:token, gid, hid
# # gid：自己表格的id，hid：别人表格的id，返回两联邦学习交叉验证的分数
# # 耗时API
# # return:result,score
# @app.route('/hetero_lr_cv')
# def hetero_lr_cv():
#     resp_json, uid = get_uid()
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     gid, hid = get_params((Params.GID, Params.HID))
#     if gid is None or hid is None:
#         resp_json[Params.RESULT] = RetVal.LACK_PARAM
#         return json.dumps(resp_json)
#     model = Model.query.filter(hid=hid, gid=gid).first()
#     if model is not None and model.score is not None:
#         resp_json[Params.RESULT] = RetVal.OK
#         resp_json[Params.SCORE] = model.score
#         return json.dumps(resp_json)
#     host_table = Table.query.get(hid)
#     guest_table = Table.query.get(gid)
#     if host_table is None or guest_table is None:
#         resp_json[Params.RESULT] = RetVal.NO_RECORD
#         return json.dumps(resp_json)
#     node = Node(uid)
#     score = node.get_hetero_lr_score(gid, guest_table, host_table.uid, host_table)
#     model = Model()
#     model.uid = uid
#     model.gid = gid
#     model.hid = hid
#     model.score = score
#     db.session.add(model)
#     resp_json = db_commit()
#     resp_json[Params.SCORE] = score
#     return json.dumps(resp_json)
#
# # /local_lr_cv
# # param:token, gid
# # gid：自己表格的id，返回本地学习交叉验证的分数
# # 耗时API
# # return:result,score
# @app.route('/local_lr_cv')
# def local_lr_cv():
#     resp_json, uid = get_uid()
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, guest_table = get_table_param(Params.GID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     node = Node(uid)
#     score = node.get_local_lr_score(guest_table.get_local_path(), guest_table.id_col, guest_table.y_col)
#     guest_table.score = score
#     resp_json = db_commit()
#     resp_json[Params.SCORE] = score
#     return json.loads(resp_json)
#
#
# # /hetero_lr_train
# # param:token,gid,hid,name,memo
# # gid：自己表格的id，hid：别人表格的id，name：训练好模型的名字，memo：备注
# # return：result
# @app.route('/hetero_lr_train')
# def hetero_lr_cv():
#     resp_json, uid = get_uid()
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, guest_table = get_table_param(Params.GID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, host_table = get_table_param(Params.HID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     model_name = get_param(Params.NAME)
#     memo = get_param(Params.MEMO)
#     node = Node(uid)
#     guest_table_path = guest_table.get_fate_path()
#     host_table_path = host_table.get_fate_path()
#     host_user_id = host_table.name.uid
#     guest_user_id = guest_table.name.uid
#     model_name_record = ModelName.Query.filter_by(hid=host_user_id, gid=guest_user_id).first()
#     if model_name_record is None:
#         if model_name is None:
#             resp_json[Params.RESULT] = RetVal.LACK_PARAM
#             return json.dumps(resp_json)
#         model_name_record = ModelName()
#         model_name_record.name = model_name
#         model_name_record.uid = uid
#         model_name_record.hid = host_table.name.id
#         model_name_record.gid = guest_table.name.id
#         db.session.add(model_name_record)
#         resp_json = db_commit()
#         if resp_json[Params.RESULT] != RetVal.OK:
#             return json.dumps(resp_json)
#         ver = 1
#         name_id = model_name_record.id
#     else:
#         model_name = model_name_record.name
#         name_id = model_name_record.id
#         model = Model.query.filter_by(name_id=name_id).order_by(Model.ver.desc()).first()
#         ver = 1 if model is None else model.ver + 1
#     guest_table_id = guest_table.id
#     host_table_id = host_table.id
#     model = Model()
#     model.name_id = name_id
#     model.ver = ver
#     model.gid = guest_table_id
#     model.hid = host_table_id
#     model.memo = memo
#     model_path = model.get_fate_path()
#     node.hetero_lr_train(guest_table_path, host_table_path, host_user_id, model_path)
#     db.session.add(model)
#     resp_json = db_commit()
#     return json.dumps(resp_json)
#
#
# # /hetero_lr_predict
# # param:token,gid,hid,mid
# # gid：guest table id，
# # hid：host table id，
# # mid：model id
# # 耗时API
# # return：result，predict [(id, label)]
# @app.route('/hetero_lr_train')
# def hetero_lr_train():
#     resp_json, uid = get_uid()
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, guest_table = get_table_param(Params.GID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, host_table = get_table_param(Params.HID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, model = get_model_param(Params.MID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     model_path = model.get_fate_path()
#     node = Node(uid)
#     guest_table_path = guest_table.get_fate_path()
#     host_table_path = host_table.get_fate_path()
#     host_uid = host_table.name.uid
#     df = node.hetero_lr_predict(guest_table_path, host_uid, host_table_path, model_path)
#     resp_json[Params.PREDICT] = df.values.tolist()
#     return json.dumps(resp_json)
#
#
#
# /topup
# param：token，amount
# 充值，该函数直接返回成功
# return：result
@app.route('/topup')
def hetero_lr_train():
    resp_json, uid = get_uid()
    if resp_json[Params.RESULT] != RetVal.OK:
        return json.dumps(resp_json)
    amount = get_param(Params.AMOUNT)
    if amount is None:
        resp_json[Params.RESULT] = RetVal.LACK_PARAM
        return json.dumps(resp_json)
    trans = Transaction()
    trans.gid = uid
    trans.amount = amount
    trans.type = TransType.TOPUP
    db.session.add(trans)
    user = User.query.get(uid)
    user.wallet += amount
    db_commit()
    return json.dumps(resp_json)
#
# # /set_price
# # param:token,gid,price0,price1,price2
# # 设置表格gid的固定价格
# # return：result
# @app.route('/set_price')
# def hetero_lr_train():
#     resp_json, uid = get_uid()
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     resp_json, guest_table = get_table_param(Params.GID)
#     if resp_json[Params.RESULT] != RetVal.OK:
#         return json.dumps(resp_json)
#     p0, p1, p2 = get_params((Params.PRICE0, Params.PRICE1, Params.PRICE2))
#     if p0 is not None and p0 > 0:
#         guest_table.price0 = p0
#     if p1 is not None and p1 > 0:
#         guest_table.price1 = p1
#     if p2 is not None and p2 > 0:
#         guest_table.price2 = p2
#     db_commit()
#


# /get_competition_tables
# param:token
# 显示当前余额下可以支持竞价的表格数,nid，节点id，tid，表格id
# return：result，[(nid, tid, table_name)]
#
# /transactions
# param:token
# 显示已发生的交易信息
# return：result,[(time, guest_id, host_id, amount)]
#
# /balance_history
# param:token
# 显示余额变化信息，type包括【0=充值，1=支出，2=收入】，amount：变动额，balance余额
# return：result,[(time, type, amount，balance)]
#
# /data_list
# param:token，count
# 按数据质量对平台数据排序，并显示前count个,nid节点id，improvement，交叉验证分数提升总和
# return:result,[(nid, table_name, improvement)]


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
