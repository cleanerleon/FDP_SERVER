import json
from concurrent.futures import ProcessPoolExecutor
import concurrent

import uuid
from multiprocessing import Process

from arch.api import eggroll
from arch.api.utils import log_utils
from fdp.fdp_workflow import FDP_WorkFlow

from federatedml.param import IntersectParam
from federatedml.statistic.intersect import RsaIntersectionHost, RawIntersectionHost, RsaIntersectionGuest, \
    RawIntersectionGuest
from federatedml.util import consts

from fdp.file_mgr import start_proc, upload_csv
from fdp.helper import ROLES, gen_job_id, gen_data_namespace, WORK_MODE, eggroll_init

LOGGER = log_utils.getLogger()


class IntersectWorkFlow(FDP_WorkFlow):
    def __init__(self, role):
        super(FDP_WorkFlow, self).__init__()
        self.role = role

    def _initialize(self):
        self._initialize_workflow_param()
        self._initialize_intersect()

    def _initialize_intersect(self):
        intersect_param = IntersectParam()
        self.intersect_param = self._load_param(intersect_param)

    def intersect(self, data_instance):

        if self.role == consts.HOST:
            ras_intersection_fun = RsaIntersectionHost
            raw_intersection_fun = RawIntersectionHost
        else:
            ras_intersection_fun = RsaIntersectionGuest
            raw_intersection_fun = RawIntersectionGuest
        if self.intersect_param.intersect_method == "rsa":
            LOGGER.info("Using rsa intersection")
            self.intersection = ras_intersection_fun(self.intersect_param)
        elif self.intersect_param.intersect_method == "raw":
            LOGGER.info("Using raw intersection")
            self.intersection = raw_intersection_fun(self.intersect_param)
        else:
            raise TypeError("intersect_method {} is not support yet".format(self.workflow_param.intersect_method))

        intersect_ids = self.intersection.run(data_instance)

        self.save_intersect_result(intersect_ids)



base_cfg = {
    "WorkFlowParam": {
        "method": "intersect",
        "intersect_data_output_namespace": "fdp_output_namespace",
    },
    "IntersectParam": {
        "intersect_method": "rsa",
        "random_bit": 128,
        "is_send_intersect_ids": True,
        "is_get_intersect_ids": True,
        "join_role": "host",
        "with_encode": True,
        "only_output_key": True
    },
    "EncodeParam": {
        "encode_method": "sha256",
        "salt": "12345",
        "base64": False
    }
}


def setup_cfg_json(nid, role, job_id, table, roles):
    party_id = ROLES[role]
    cfg = base_cfg.copy()
    cfg['local'] = {'role': role, 'party_id': party_id}
    cfg['role'] = {key:[ROLES[key]] for key in (consts.GUEST, consts.HOST)}
    cfg['WorkFlowParam']['data_input_table'] = table
    cfg['WorkFlowParam']['data_input_namespace'] = gen_data_namespace(nid)
    cfg['WorkFlowParam']['intersect_data_output_table'] = role + '_intersect_output_' + job_id
    return json.loads(json.dumps(cfg))


def role_jobs(nid, role, job_id, table, roles):
    cfg = setup_cfg_json(nid, role, job_id, table, roles)
    node = IntersectWorkFlow(role)
    # ns = gen_data_namespace(nid)
    # eggroll.init(job_id, WORK_MODE)
    # etable = eggroll.table(name=table, namespace=ns)
    # print(ns, table, ' count:', etable.count())
    node.run(cfg, job_id)


def get_cross_size(gpid, guid, g_table, hpid, huid, h_table):
    job_id = gen_job_id(hpid, gpid)
    roles = {consts.HOST: [hpid], consts.GUEST: [gpid]}
    args=((huid, consts.HOST, job_id, h_table, roles),
          (guid, consts.GUEST, job_id, g_table, roles))
    # ps = [Process(target=role_jobs, args=arg) for arg in args]
    # for p in ps:
    #     p.start()
    # for p in ps:
    #     p.join()
    # print('processes done')

    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(role_jobs, *arg): arg[1] for arg in args}
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(str(exc))

    intersect_table = consts.GUEST + '_intersect_output_' + job_id
    intersect_namespace = 'fdp_output_namespace'
    eggroll.init(job_id, WORK_MODE)
    table = eggroll.table(
        name=intersect_table,
        namespace=intersect_namespace,
    )
    table_size = table.count()
    return table_size


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

    job_id = str(uuid.uuid1())
    args=((host_a_id, consts.HOST, job_id, host_a_table), (guest_id, consts.GUEST, job_id, guest_table))

    start_proc(upload_csv, guest_id, guest_file, guest_table)
    start_proc(upload_csv, host_a_id, host_a_file, host_a_table)

    ret = get_cross_size(guest_id, guest_table, host_a_id, host_a_table)
    print('intersection size:', ret)
