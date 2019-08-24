import datetime
from arch.api import RuntimeInstance, eggroll

ROLES = {'host': 9999, 'arbiter': 10000, 'guest': 10000}
WORK_MODE = 0
ARBITER_NID = 0
PREDICT_NAMESPACE = 'fdp_output_namespace'

guest_file = "../examples/data/lite_b.csv"
host_file = "../examples/data/lite_a.csv"


def gen_job_id(hpid, gpid):
    job_id = 'dfp_h%d_g%d_' % (hpid, gpid) + datetime.datetime.now().strftime('%Y%m%d_%H_%M_%S')
    print('job_id:', job_id)
    return job_id


def gen_data_namespace(node_id):
    return 'fdp_input_data_node' + str(node_id)


def gen_model_namespace(node_id):
    return 'fdp_model_node' + str(node_id)


def eggroll_init():
    if RuntimeInstance.EGGROLL is None:
        eggroll.init(job_id='file_op', mode=WORK_MODE)
