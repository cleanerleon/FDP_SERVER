from enum import IntEnum
import logging
from logging.handlers import TimedRotatingFileHandler
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from threading import RLock

from flask import request, session

from server.model.Model import Model
from server.model.Table import Table
from server import db, app
from server.model.TableName import TableName

class TransType(IntEnum):
    TOPUP = 0
    TRAIN = 1
    AUTO_TRAIN = 2
    PREDICT = 3

class RetVal(IntEnum):
    OK = 0
    LACK_PARAM = 1
    NO_RECORD = 2
    DB_FAILURE = 3
    FILE_INV = 4
    TOKEN_INV = 5
    DB_DUP = 6
    FILE_LARGE = 7
    NO_Y = 8
    NO_MONEY = 9
    NO_IMPV = 10
    SIZE_0 = 11


class Params:
    RESULT = 'result'
    TOKEN = 'token'
    PASSWORD = 'password'
    ID = 'id'
    UID = 'uid'
    NID = 'nid'
    HTID = 'htid'
    GTID = 'gtid'
    MID = 'mid'
    ID_COL = 'id_col'
    LABEL_COL = 'label_col'
    TABLE_NAME = 'table_name'
    MEMO = 'memo'
    TABLES = 'tables'
    NAME = 'name'
    TABLE = 'table'
    USERS = 'users'
    VER = 'ver'
    TIME = 'time'
    COST = 'cost'
    SIZE = 'size'
    IMPV = 'impv'
    SCORE = 'score'
    PREDICT = 'predict'
    PRICE0 = 'p0'
    PRICE1 = 'p1'
    PRICE2 = 'p2'


class Logger:
    lock = RLock()
    LEVEL = logging.DEBUG
    logger = None

    @staticmethod
    def get_logger():
        if Logger.logger:
            return Logger.logger
        with Logger.lock:
            if Logger.logger is None:
                logger = logging.getLogger('FDP')
                formatter = logging.Formatter('"%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s"')
                log_file = 'fdp.log'
                handler = TimedRotatingFileHandler(log_file,
                                                   when='H',
                                                   interval=4,
                                                   backupCount=7,
                                                   delay=True)

                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.addHandler(logging.StreamHandler())
                logger.setLevel(Logger.LEVEL)
                Logger.logger = logger
        return Logger.logger


def is_param_set(param):
    return param is not None and len(param) > 0


def db_commit():
    try:
        db.session.commit()
        ret = RetVal.OK.value
    except SQLAlchemyError as e:
        print('db_commit exception:', e)
        logger = Logger.get_logger()
        logger.error('db_commit exception: %s', str(e))
        if type(e) is IntegrityError:
            ret = RetVal.DB_DUP.value
        else:
            ret = RetVal.DB_FAILURE.value
        db.session.rollback()
    resp_json = {Params.RESULT: ret}
    return resp_json


def get_table_param(key):
    table_id = get_param(key)
    if table_id is None:
        resp_json ={Params.RESULT: RetVal.LACK_PARAM.value}
        return resp_json, None
    table = Table.query.get(table_id)
    ret = RetVal.NO_RECORD.value if table is None else RetVal.OK.value
    resp_json ={Params.RESULT: ret}
    return resp_json, table


def get_model_param(key):
    model_id = get_param(key)
    if model_id is None:
        resp_json ={Params.RESULT: RetVal.LACK_PARAM.value}
        return resp_json, None
    model = Model.query.get(model_id)
    ret = RetVal.NO_RECORD.value if model is None else RetVal.OK.value
    resp_json ={Params.RESULT: ret}
    return resp_json, model


def get_param(name):
    if request.method == 'GET':
        if name in request.args:
            return request.args[name]
    else:
        if name in request.form:
            return request.form[name]
    return None


def get_uid():
    # if app.debug:
    #     uid = 1
    #     ret = RetVal.OK.value
    #     resp_json = {Params.RESULT: ret}
    #     return resp_json, uid
    token = get_param(Params.TOKEN)
    if token is None or token != session[Params.TOKEN]:
        ret = RetVal.TOKEN_INV.value
        uid = None
    else:
        ret = RetVal.OK.value
        uid = session[Params.UID]
    resp_json = {Params.RESULT: ret}
    return resp_json, uid


def get_params(keys):
    return [get_param(key) for key in keys]


