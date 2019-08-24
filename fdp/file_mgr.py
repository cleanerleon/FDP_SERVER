import csv
from multiprocessing import Process

import os

from arch.api import eggroll, StoreType
from arch.api.storage import save_data
from arch.api.standalone.eggroll import Standalone
from arch.api.utils import file_utils

from fdp.helper import WORK_MODE, gen_data_namespace, gen_model_namespace, eggroll_init


def list_to_str(input_list):
    str1 = ''
    size = len(input_list)
    for i in range(size):
        if i == size - 1:
            str1 += str(input_list[i])
        else:
            str1 += str(input_list[i]) + ','

    return str1


def csv_read_data(input_file, head=True):
    with open(input_file) as csv_file:
        csv_reader = csv.reader(csv_file)
        if head:
            next(csv_reader)
        for row in csv_reader:
            yield (row[0], list_to_str(row[1:]))


def upload_csv(nid, path, table_name):
    eggroll_init()
    # df = pd.read_csv(path, index_col=id_col)
    # if label_col is not None:
    #     df[label_col] = df[label_col].astype('bool')
    # kv_data = [(idx, ','.join(row.astype(str).values)) for idx, row in df.iterrows()]
    kv_data = csv_read_data(path)
    namespace = gen_data_namespace(nid)
    return save_data(kv_data, name=table_name, namespace=namespace, error_if_exist=True)


def start_proc(func, *args):
    proc = Process(target=func, args=args)
    proc.start()
    proc.join()


def upload_csv_proc(nid, path, table_name):
    proc = Process(target=upload_csv, args=(nid, path, table_name))
    proc.start()
    proc.join()


def list_files(namespace):
    _type = StoreType.LMDB.value
    _base_dir = os.sep.join([os.path.join(file_utils.get_project_base_directory(), 'data'), _type])
    _namespace_dir = os.sep.join([_base_dir, namespace])
    if not os.path.isdir(_base_dir):
        raise EnvironmentError("illegal datadir")
    return [file for file in os.listdir(_namespace_dir) if not file.endswith('.meta')]


def list_tables(nid):
    return list_files(gen_data_namespace(nid))


def list_models(nid):
    return list_files(gen_model_namespace(nid))


def del_table(nid, name):
    eggroll_init()
    eggroll.cleanup(name, gen_data_namespace(nid), True)


def del_model(nid, name):
    eggroll_init()
    eggroll.cleanup(name, gen_model_namespace(nid), True)


def show_table(nid, table_name):
    eggroll_init()
    table = eggroll.table(table_name, gen_data_namespace(nid))
    data = list(table.collect())
    print(data)

if __name__ == '__main__':
    pass
    # from fdp.helper import guest_file, host_file
    # gid = 1
    # hid = 2
    # g_table = 'guest_table'
    # h_table = 'host_table'
    # for item in ((gid, guest_file, g_table), (hid, host_file, h_table)):
    #     upload_csv_proc(*item)
    #
    # for i in (gid, hid):
    #     print('nid:', i)
    #     print('list tables')
    #     tables = list_tables(i)
    #     for table in tables:
    #         print(table)
    #         del_table(i, table)
    #     print('delete tables')
    #     print(list_tables(i))
    #
    # for item in ((gid, guest_file, g_table), (hid, host_file, h_table)):
    #     upload_csv_proc(*item)
    #
    # for i in (gid, hid):
    #     print('nid:', i)
    #     print('list tables')
    #     tables = list_tables(i)
    #     for table in tables:
    #         print(table)