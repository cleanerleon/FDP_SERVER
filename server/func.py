import concurrent
import json
import multiprocessing
import shutil

import os
from decimal import Decimal

import numpy as np
import pandas as pd

from fdp.Node import Node
from fdp.fl_intersect import get_cross_size
from fdp.hetero_lr import cv, train, predict
from server import db, app
from server.helper import Params, RetVal, db_commit, is_param_set, TransType
from server.model.ModelName import ModelName
from server.model.CVResult import CVResult
from server.model.Model import Model
from server.model.SizeResult import SizeResult
from server.model.Table import Table
from server.model.TableName import TableName
from server.model.Transaction import Transaction
from server.model.User import User


MAX_ROW = 1000
MAX_COLUMN = 25

def _check_cross_size(guid, guest_table, host_table):
    size_result = SizeResult.query.filter_by(hid=host_table.id, gid=guest_table.id).first()
    if size_result is None:
        size_result = SizeResult.query.filter_by(hid=guest_table.id, gid=host_table.id).first()
    if size_result is None:
        guest_table_path = guest_table.get_fate_path()
        host_table_path = host_table.get_fate_path()
        gpid = 1
        hpid = 2
        htid = host_table.id
        gtid = guest_table.id
        guid = guest_table.name.uid
        huid = host_table.name.uid
        size = get_cross_size(gpid, guid, guest_table_path, hpid, huid, host_table_path)
        size_result = SizeResult()
        size_result.gid = gtid
        size_result.hid = htid
        size_result.size = size
        db.session.add(size_result)
        db_commit()
    print('GUEST TABLE ID %d HOST TABLE ID %d 交集大小 %d' %
          (guest_table.id, host_table.id, size_result.size))
    if size_result.size == 0:
        return {Params.RESULT: RetVal.SIZE_0.value}
    else:
        return {Params.RESULT: RetVal.OK.value}

def _check_balance(guid, guest_table, host_table, mode):
    # check balance
    user = User.query.get(guid)
    size_result = SizeResult.query.filter_by(hid=host_table.id, gid=guest_table.id).first()
    if user is None or size_result is None:
        return {Params.RESULT: RetVal.NO_RECORD.value}
    price = host_table.price0 if mode == TransType.TRAIN.value else host_table.price1
    cost = price * size_result.size
    print('GUEST ID %d 余额 %.2f'% (guid, user.balance))
    print('GUEST TABLE ID %d HOST TABLE ID %d 训练成本 %.2f' %
          (guest_table.id, host_table.id, cost))
    if cost > user.balance:
        return {Params.RESULT: RetVal.NO_MONEY.value}
    else:
        return {Params.RESULT: RetVal.OK.value, Params.COST: cost}


def _check_cv(guid, guest_table, host_table):
    # calculate local cv
    if not is_param_set(guest_table.y_col):
        return {Params.RESULT: RetVal.NO_Y.value}
    if guest_table.score is None or guest_table.score == 0:
        score = Node.get_local_lr_score(guest_table.get_local_path(), guest_table.id_col, guest_table.y_col)
        guest_table.score = float(score)

        resp_json = db_commit()
        if resp_json[Params.RESULT] != RetVal.OK.value:
            return resp_json
    print('GUEST TABLE ID %d 本地训练分数: %.4f' % (guest_table.id, guest_table.score))

    # hetero lr cv
    gtid = guest_table.id
    htid = host_table.id
    huid = host_table.name.uid
    cv_result = CVResult.query.filter_by(hid=htid, gid=gtid).first()
    if cv_result is None:
        cv_score = cv(guid, guest_table.get_fate_path(), guest_table.y_col_id, huid, host_table.get_fate_path(), host_table.y_col_id)
        auc_score = float(np.mean(cv_score['auc']))
        cv_result = CVResult()
        cv_result.hid = htid
        cv_result.gid = gtid
        cv_result.score = auc_score
        cv_result.score_gap = auc_score - guest_table.score
        db.session.add(cv_result)
        resp_json = db_commit()
        if resp_json[Params.RESULT] != RetVal.OK.value:
            return resp_json
        db_commit()
    print('GUEST TABLE ID %d HOST TABLE ID %d 在线训练分数 %.4f, %.4f %s than 本地模型' %
          (guest_table.id, host_table.id, cv_result.score, abs(cv_result.score_gap),
          'higher' if cv_result.score_gap >= 0 else 'lower'))
    if cv_result.score_gap <= 0:
        return {Params.RESULT: RetVal.NO_IMPV.value}
    else:
        return {Params.RESULT: RetVal.OK.value,
                Params.IMPV: cv_result.score_gap}


def _train(guid, guest_table, host_table, mode, cost, memo=''):
    user = User.query.get(guid)

    # hetero lr train
    gtid = guest_table.id
    htid = host_table.id
    huid = host_table.name.uid
    model = Model.query.filter_by(gid=gtid, hid=htid).first()
    if model is None:
        hnid = host_table.name.id
        gnid = guest_table.name.id
        model_name = ModelName.query.filter_by(uid=guid, hid=hnid, gid=gnid).first()
        if model_name is None:
            model_name = ModelName()
            model_name.uid = guid
            model_name.gid = gnid
            model_name.hid = hnid
            model_name.name = 'model_u%d_g%d_h%d' % (guid, gnid, hnid)
            db.session.add(model_name)
            resp_json = db_commit()
            if resp_json[Params.RESULT] != RetVal.OK.value:
                return resp_json
        model = Model.query.filter_by(name_id=model_name.id).order_by(Model.ver.desc()).first()
        ver = 1 if model is None else model.ver + 1
        model = Model()
        model.name_id = model_name.id
        model.gid = gtid
        model.hid = htid
        model.ver = ver
        model.memo = memo
        db.session.add(model)
        resp_json = db_commit()
        if resp_json[Params.RESULT] != RetVal.OK.value:
            return resp_json
        model_path = model.get_fate_path()
        train(guid, guest_table.get_fate_path(), guest_table.y_col_id, \
              huid, host_table.get_fate_path(), host_table.y_col_id, model_path)
        print('模型 %s 版本 %d ID %d 备注 \"%s\"' %
              (model.name.name, model.ver, model.id, model.memo))
        user.balance -= cost
        host = User.query.get(host_table.name.uid)
        host.balance += cost
        trans = Transaction()
        trans.gid = guid
        trans.hid = huid
        trans.amount = cost
        trans.type = mode
        db.session.add(trans)
        resp_json = db_commit()
        print('GUEST ID %d 支出 %.2f' % (guid, cost))
        print('HOST ID %d 收入 %.2f' % (host.id, cost))
        print('交易ID %d 发生' % trans.id)

    return {Params.RESULT: RetVal.OK}


def func_train(guid, guest_table, host_table, memo=''):
    mode = TransType.TRAIN.value
    resp_json = _check_cross_size(guid, guest_table, host_table)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return resp_json
    resp_json = _check_balance(guid, guest_table, host_table, mode)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return resp_json
    cost = resp_json[Params.COST]
    resp_json = _check_cv(guid, guest_table, host_table)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return resp_json
    resp_json = _train(guid, guest_table, host_table, mode, cost, memo)
    return resp_json


def func_auto_train(guid, guest_table, memo):
    users = User.query.filter(User.id != guid).all()
    table_info_list = []
    mode = TransType.AUTO_TRAIN.value
    for user in users:
        for table_name in user.table_names:
            for host_table in table_name.tables:
                resp_json = _check_cross_size(guid, guest_table, host_table)
                if resp_json[Params.RESULT] != RetVal.OK.value:
                    continue
                resp_json = _check_balance(guid, guest_table, host_table, mode)
                # print('_check_balance ',resp_json)
                if resp_json[Params.RESULT] != RetVal.OK.value:
                    continue
                cost = resp_json[Params.COST]
                resp_json = _check_cv(guid, guest_table, host_table)
                # print('_check_cv ',resp_json)
                if resp_json[Params.RESULT] != RetVal.OK.value:
                    continue
                score_gap = resp_json[Params.IMPV]
                table_info_list.append((host_table.id, score_gap, cost))
    table_info_list.sort(key=lambda x:x[1], reverse=True)
    if len(table_info_list) == 0:
        return {Params.RESULT: RetVal.NO_IMPV.value}
    host_table_id, score_gap, cost = table_info_list[0]
    resp_json = _train(guid, guest_table, host_table, mode, cost, memo)
    return resp_json


def func_get_target_tables(guid, guest_table, mode):
    gtid = guest_table.id;
    user = User.query.get(guid)
    balance = user.balance
    table_names = TableName.query.filter(TableName.uid != guid).all()
    tables = [(table.id, table_name.uid, table.get_fate_path(), \
               table.price0, table.price1, table.price2) \
              for table_name in table_names for table in table_name.tables]
    results = SizeResult.query.filter(SizeResult.hid == gtid or SizeResult.gid == gtid).all()
    htids = set([result.hid if result.gid == gtid else result.hid for result in results])
    guest_table_path = guest_table.get_fate_path()
    args = [(huid, htid, host_table_path) for htid, huid, host_table_path, p0, p1, p2 in tables if htid not in htids]

    for i, (huid, htid, host_table_path) in enumerate(args):
        gpid = i * 2 + 2
        hpid = i * 2 + 1
        size = get_cross_size(gpid, guid, guest_table_path, hpid, huid, host_table_path)
        # print('host_table %s: %d' % (host_table_path, size))
        result = SizeResult()
        result.gid = gtid
        result.hid = htid
        result.size = size
        db.session.add(result)

    # with concurrent.futures.ProcessPoolExecutor(max_workers=6) as executor:
    #     futures = {executor.submit(get_cross_size, i*2+2, uid, guest_table_path, i*2+1, huid, host_table_path): htid \
    #                for i, (huid, htid, host_table_path) in enumerate(args)}
    #     for future in concurrent.futures.as_completed(futures):
    #         htid = futures[future]
    #         try:
    #             size = future.result()
    #             print(htid, ' ', size)
    #             result = SizeResult()
    #             result.gid = gtid
    #             result.hid = htid
    #             result.size = size
    #             # db.session.add(result)
    #         except Exception as exc:
    #             print('generated an exception: %s' % (exc))
    resp_json = db_commit()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return  resp_json

    results = SizeResult.query.filter((SizeResult.hid == gtid)).all()
    if mode == TransType.TRAIN.value:
        price_map = {htid: p0 for htid, _ , _, p0, p1, p2 in tables}
    elif mode == TransType.AUTO_TRAIN.value:
        price_map = {htid: p1 for htid, _ , _, p0, p1, p2 in tables}
    else:
        price_map = {htid: p1 for htid, _ , _, p0, p1, p3 in tables}
    tables = [result.gid for result in results if result.size * price_map[result.gid] <= balance]
    results = SizeResult.query.filter((SizeResult.gid == gtid)).all()
    tables.extend([result.hid for result in results if result.size * price_map[result.hid] <= balance])
    resp_json={Params.RESULT: RetVal.OK.value, Params.TABLES: tables}
    return resp_json


def func_topup(guid, amount):
    user = User.query.get(guid)
    user.balance += Decimal(amount)
    trans = Transaction()
    trans.gid = guid
    trans.amount = amount
    trans.type = TransType.TOPUP.value
    db.session.add(trans)
    return db_commit()


def func_show_hosts(uid):
    users = User.query.filter(User.id!=uid).all()
    resp_json = {Params.RESULT: RetVal.OK.value,
                 Params.USERS: [{Params.ID: user.id, Params.NAME: user.name} for user in users]}
    return resp_json


def func_show_table(uid, table):
    if table.name.uid != uid:
        resp_json = {Params.RESULT: RetVal.NO_RECORD.value}
        return resp_json
    df = pd.read_csv(table.get_local_path())
    data = []
    data.append(df.columns.tolist())
    data.extend(df.values.tolist())
    resp_json = {Params.RESULT: RetVal.NO_RECORD.value, Params.TABLE:data}
    return resp_json


def func_get_tables(uid):
    table_names = TableName.query.filter_by(uid=uid).order_by(TableName.id.desc()).all()
    tables = [{Params.NID: table_name.id,
               Params.NAME: table_name.name,
               Params.TABLE:{
                   Params.GTID: table.id,
                   Params.VER: table.ver,
                   Params.TIME: table.time,
                   Params.MEMO: table.memo,
                   Params.PRICE0: table.price0,
                   Params.PRICE1: table.price1,
                   Params.PRICE2: table.price2
               }}
              for table_name in table_names for table in table_name.tables]
    resp_json = {Params.TABLES: tables, Params.RESULT: RetVal.OK.value}
    return resp_json


def func_set_price(uid, table, p0, p1, p2):
    if table.name.uid != uid:
        return {Params.RESULT: RetVal.NO_RECORD.value}
    if p0 is not None and p0 > 0:
        table.price0 = p0
    if p1 is not None and p1 > 0:
        table.price1 = p1
    if p2 is not None and p2 > 0:
        table.price2 = p2
    return db_commit()


def func_predict(mid, guest_table, host_table):
    model = Model.query.get(mid)
    guid = guest_table.name.user.id
    huid = host_table.name.user.id
    guest = User.query.get(guid)
    host = User.query.get(huid)
    resp_json = _check_cross_size(guid, guest_table, host_table)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return resp_json

    df = predict(guid, guest_table.get_fate_path(), guest_table.y_col_id, huid, \
                 host_table.get_fate_path(), host_table.y_col_id, model.get_fate_path())
    print(df.head())
    resp_json = _check_balance(guid, guest_table, host_table, TransType.PREDICT.value)
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return resp_json
    cost = resp_json[Params.COST]
    guest.balance -= cost
    host.balance += cost
    trans = Transaction()
    trans.gid = guid
    trans.hid = huid
    trans.amount = cost
    trans.type = TransType.PREDICT.value
    db.session.add(trans)
    db_commit()
    print('GUEST ID %d paid %.2f' % (guid, cost))
    print('HOST ID %d received %.2f' % (host.id, cost))
    print('TRANSACTION ID %d occurred' % trans.id)


def func_show_trans(uid):
    trans = Transaction.query.filter(Transaction.hid == uid or Transaction.gid == uid).all()
    type_str = {TransType.TOPUP.value: '充值',
                TransType.TRAIN.value: '定价训练',
                TransType.AUTO_TRAIN.value: '竞价训练',
                TransType.PREDICT.value: '预测'}
    for tran in trans:
        if tran.type in set((TransType.TRAIN.value, TransType.AUTO_TRAIN.value, TransType.PREDICT.value)):
            tran_str = '支出' if tran.gid == uid else '收入'
        else:
            tran_str = ''

        print('TRANS ID %d, %s, %s, %.2f' % (tran.id, tran.time, type_str[tran.type]+tran_str, tran.amount))


def func_show_data():
    tables = Table.query.all()
    table_scores = []
    for table in tables:
        htid = table.id
        total_score_gap = 0
        total_size = 0
        cv_results = CVResult.query.filter_by(hid=htid).all()

        for cv_result in cv_results:
            if cv_result.score_gap > 0:
                gtid = cv_result.gid
                size_result = SizeResult.query.filter((SizeResult.gid==gtid and SizeResult.hid==htid) or \
                                                      (SizeResult.hid==htid and SizeResult.gid==gtid)).first()
                size = size_result.size
                total_size += size
                total_score_gap += cv_result.score_gap
        table_scores.append((htid, total_size, total_score_gap, total_score_gap / total_size if total_size > 0 else 0))
    table_scores.sort(key=lambda x:x[3], reverse=True)
    for score in table_scores:
        print('TABLE ID %d 参与联邦学习数据%d条， 模型改善分数总计%.4f， 平均%.8f' % (score[0], score[1], score[2], score[3]))


def func_add_table_name(uid, table_name):
    table_name_rec = TableName()
    table_name_rec.uid = uid
    table_name_rec.name = table_name
    db.session.add(table_name_rec)
    db_commit()


def func_update_table(tnid, path, id_col, y_col, memo):
    # save table record to get name
    t_rec = Table()
    t_rec.name_id = tnid
    t_rec.memo = memo
    t_rec.id_col = id_col
    t_rec.y_col = y_col
    db.session.add(t_rec)
    resp_json = db_commit()
    if resp_json[Params.RESULT] != RetVal.OK.value:
        return json.dumps(resp_json)

    # check csv file
    local_path = t_rec.get_local_path()
    shutil.copyfile(path, local_path)
    uid = t_rec.name.uid
    try:
        df = pd.read_csv(local_path)
        resp_json[Params.RESULT] = RetVal.OK.value
    except Exception as e:
        os.unlink(local_path)
        resp_json[Params.RESULT] = RetVal.FILE_INV.value
        df = None

    if df is not None:
        r, c = df.shape
        if r <= MAX_ROW and c <= MAX_COLUMN and id_col in df.columns:
            if y_col in df.columns:
                label_id = df.drop(id_col, axis=1).columns.get_loc(y_col)
            elif len(y_col) == 0:
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
