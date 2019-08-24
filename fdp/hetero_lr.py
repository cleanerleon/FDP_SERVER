import concurrent
import pandas as pd

from fdp.fdp_workflow import FDP_WorkFlow
from fdp.file_mgr import list_models, start_proc, upload_csv
from fdp.helper import ROLES, gen_data_namespace, ARBITER_NID, gen_job_id, gen_model_namespace, WORK_MODE, \
    PREDICT_NAMESPACE
from federatedml.logistic_regression.hetero_logistic_regression import HeteroLRHost, HeteroLRGuest, HeteroLRArbiter
from federatedml.param.param import LogisticParam
import json
from arch.api import eggroll

from federatedml.util import consts


base_cfg = {'DataIOParam': {'with_label': False, 'output_format': 'dense'},
            'WorkFlowParam': {'method': 'cross_validation',
                              'train_input_table': '',
                              'train_input_namespace': '',
                              'model_table': '',
                              'model_namespace': '',
                              'predict_input_table': '',
                              'predict_input_namespace': '',
                              'predict_output_table': '',
                              'predict_output_namespace': 'fdp_output_namespace',
                              'evaluation_output_table': '',
                              'evaluation_output_namespace': 'fdp_output_namespace',
                              'data_input_table': '',
                              'data_input_namespace': '',
                              'work_mode': 0,
                              'n_split': 5,
                              'need_intersect': True,
                              'need_feature_selection': False,
                              'need_scale': False,
                              'need_one_hot': False,
                              'one_vs_rest': False},
            'OneHotEncoderParam': {'cols': ['fid0']},
            'EncryptParam': {'method': 'Paillier', 'key_length': 1024},
            'InitParam': {'init_method': 'random_uniform', 'fit_intercept': True},
            'EvaluateParam': {'metrics': ['auc'],
                              'classi_type': 'binary',
                              'pos_label': 1,
                              'thresholds': [0.5]},
            'LogisticParam': {'penalty': 'L2',
                              'optimizer': 'rmsprop',
                              'eps': 0.0001,
                              'alpha': 0.01,
                              'max_iter': 10,
                              'converge_func': 'diff',
                              'batch_size': -1,
                              'learning_rate': 0.15},
            'IntersectParam': {'intersect_method': 'raw',
                               'is_send_intersect_ids': True,
                               'join_role': 'guest',
                               'with_encode': True},
            'EncodeParam': {'encode_method': 'sha256', 'salt': '12345', 'base64': False},
            'PredictParam': {'with_proba': True, 'threshold': 0.5},
            'ScaleParam': {'method': 'min_max_scale',
                           'mode': 'normal',
                           'area': 'all',
                           'feat_upper': None,
                           'feat_lower': None,
                           'out_upper': None,
                           'out_lower': None},
            'FeatureBinningParam': {'method': 'quantile',
                                    'compress_thres': 10000,
                                    'head_size': 10000,
                                    'error': 0.001,
                                    'adjustment_factor': 0.5,
                                    'bin_num': 10,
                                    'cols': -1,
                                    'local_only': False,
                                    'result_table': 'TO SET',
                                    'result_namespace': 'TO SET',
                                    'display_result': ['iv']},
            'FeatureSelectionParam': {'method': 'fit',
                                      'filter_method': ['unique_value',
                                                        'iv_value_thres',
                                                        'coefficient_of_variation_value_thres',
                                                        'outlier_cols'],
                                      'select_cols': -1,
                                      'local_only': False,
                                      'result_table': 'feature_selection_guest_model_table',
                                      'result_namespace': 'feature_select_namespace'},
            'UniqueValueParam': {'eps': 1e-05},
            'IVSelectionParam': {'value_threshold': 0.1, 'percentile_threshold': 1.0},
            'CoeffOfVarSelectionParam': {'value_threshold': 0.1,
                                         'percentile_threshold': 0.8},
            'OutlierColsSelectionParam': {'percentile': 0.9, 'upper_threshold': 1000},
            'EncryptedModeCalculatorParam': {'mode': 'strict', 're_encrypted_rate': 1},
            'OneVsRestParam': {'has_arbiter': True}}


def setup_cfg(nid, role, job_id, method, table_name=None, y_id=-1, model_name=None):
    cfg = base_cfg.copy()
    cfg['local'] = {'role': role, 'party_id': ROLES[role]}
    cfg['role'] = {key: [value] for key, value in ROLES.items()}
    cfg['WorkFlowParam']['method'] = method
    data_namespace = gen_data_namespace(nid)
    if table_name is not None:
        cfg['WorkFlowParam']['data_input_table'] = table_name
        cfg['WorkFlowParam']['train_input_table'] = table_name
        cfg['WorkFlowParam']['predict_input_table'] = table_name
        cfg['WorkFlowParam']['predict_output_table'] = role + '_predict_table_' + job_id
        cfg['WorkFlowParam']['evaluation_output_table'] = role + '_evaluation_table_' + job_id
        cfg['WorkFlowParam']['train_input_namespace'] = data_namespace
        cfg['WorkFlowParam']['predict_input_namespace'] = data_namespace
        cfg['WorkFlowParam']['data_input_namespace'] = data_namespace
    if model_name is not None:
        cfg['WorkFlowParam']['model_table'] = model_name
        cfg['WorkFlowParam']['model_namespace'] = gen_model_namespace(nid)
    cfg['DataIOParam']['with_label'] = (y_id >= 0)
    cfg['DataIOParam']['label_idx'] = y_id
    cfg['DataIOParam']['label_type'] = 'int'

    # if role == consts.GUEST:
    #     if method == 'predict':
    #         cfg['DataIOParam']['with_label'] = False
    #     else:
    #         cfg['DataIOParam']['with_label'] = True
    #     cfg['DataIOParam']['missing_fill'] = True
    #     cfg['DataIOParam']['label_idx'] = 0
    #     cfg['DataIOParam']['label_type'] = 'int'
    return json.loads(json.dumps(cfg))


class FDP_LRWorkFlow(FDP_WorkFlow):
    def __init__(self, role):
        super(FDP_WorkFlow, self).__init__()
        self.role = role

    def _initialize_intersect(self):
        pass

    def _initialize_model(self):
        logistic_param = LogisticParam()
        self.logistic_param = self._load_param(logistic_param)
        if self.role == consts.GUEST:
            self.model = HeteroLRGuest(self.logistic_param)
        elif self.role == consts.ARBITER:
            self.model = HeteroLRArbiter(self.logistic_param)
        elif self.role == consts.HOST:
            self.model = HeteroLRHost(self.logistic_param)
        else:
            raise Exception('not support role:', self.role)

    def _initialize_role_and_mode(self):
        self.mode = consts.HETERO

    # arbiter do nothing while predict
    def predict(self, data_instance):
        if self.role == consts.ARBITER:
            return
        return super().predict(data_instance)


def role_jobs(nid, role, job_id, method, table_name=None, y_id=-1, model_name=None):
    config_json = setup_cfg(nid, role, job_id, method, table_name, y_id, model_name)
    node = FDP_LRWorkFlow(role)
    node.run(config_json, job_id)
    if role == consts.GUEST:
        if method == 'cross_validation':
            return node.cv_result


def run_jobs(guid, g_table, gy_id, huid, h_table, hy_id, job_id, method, model_name=None):
    param1 = (guid, consts.GUEST, job_id, method, g_table, gy_id, model_name)
    param2 = (huid, consts.HOST, job_id, method, h_table, hy_id)
    param3 = (ARBITER_NID, consts.ARBITER, job_id, method)
    if method == 'predict':
        args = (param1, param2)
    else:
        args = (param1, param2, param3)
    # procs = [Process(target=role_jobs, args=arg) for arg in (param1, param2, param3)]
    # for proc in procs:
    #     proc.start()
    # for proc in procs:
    #     proc.join()
    guest_ret = None
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(role_jobs, *arg): arg[1] for arg in args}
        for future in concurrent.futures.as_completed(futures):
            role = futures[future]
            try:
                ret_val = future.result()
                if role == consts.GUEST and method == 'cross_validation':
                    guest_ret = ret_val
            except Exception as exc:
                print(str(exc))
    return guest_ret


def cv(guid, g_table, gy_id, huid, h_table, hy_id):
    job_id = gen_job_id(huid, guid)
    cv_result = run_jobs(guid, g_table, gy_id, huid, h_table, hy_id, job_id, 'cross_validation')
    print('cv_result:', cv_result)
    return cv_result


def train(guid, g_table, gy_id, huid, h_table, hy_id, model_name):
    job_id = gen_job_id(huid, guid)
    run_jobs(guid, g_table, gy_id, huid, h_table, hy_id, job_id, 'train', model_name)


def predict(gid, g_table, gy_id, hid, h_table, hy_id, model_name):
    job_id = gen_job_id(hid, gid)
    run_jobs(gid, g_table, gy_id, hid, h_table, hy_id, job_id, 'predict', model_name)
    eggroll.init(job_id, WORK_MODE)
    predict_output = consts.GUEST + '_predict_table_' + job_id
    table = eggroll.table(predict_output, PREDICT_NAMESPACE)
    result = list(table.collect())
    items = [(a, b, c) for a, (b, c, d) in result]
    return pd.DataFrame.from_records(items, columns=['id', 'label', 'prob'])


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
    model_name = 'hetero_lr_guest_model_1'
    gdf = pd.read_csv(guest_file)
    print(gdf.shape)
    hdf = pd.read_csv(host_a_file)
    print(hdf.shape)


    start_proc(upload_csv, guest_id, guest_file, guest_table)
    start_proc(upload_csv, host_a_id, host_a_file, host_a_table)
    print('cv')
    ret = cv(guest_id, guest_table, 0, host_a_id, host_a_table, -1)
    print(ret)
    print('train')
    train(guest_id, guest_table, 0, host_a_id, host_a_table, -1, model_name)
    print('list_models')
    print(list_models(guest_id))
    print('predict')
    df = predict(guest_id, guest_table, 0, host_a_id, host_a_table, -1, model_name)
    print(df.shape)
