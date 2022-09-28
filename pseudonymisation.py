import json
import argparse
from datetime import datetime
from jsonpath_ng.ext import parse
import uuid
import re

parser = argparse.ArgumentParser()
parser.add_argument(
    '--psddatetime', help='time of pseudonmised resources to use format: 2022-09-26_10-03-40', nargs="?", default=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

args = vars(parser.parse_args())
psd_date_time = args["psddatetime"]


def obfuscate_date_to_year(field_input):
    return field_input[0:4]


def obfuscate_date_to_day(field_input):
    return field_input[0:10]


def remove_from_object_by_expression(to_remove, resource):
    jsonpath_expression = parse(to_remove)

    found = jsonpath_expression.find(resource)
    for match in found:
        path = [str(match.path)]
        match = match.context

        while match.context is not None:
            path = [str(match.path)] + path
            match = match.context

        for index in range(0, len(path) - 1):
            cur_key = path[index]
            if "[" in cur_key:
                cur_key = re.sub(r"[\[\]]", "", cur_key)
                cur_key = int(cur_key)
            resource = resource[cur_key]

        del resource[path[len(path)-1]]


def change_id_in_obj_by_expression(id_change, resource):

    jsonpath_expression = parse(id_change['path_to_id'])
    id_pool_name = id_change['id_pool']
    if id_pool_name not in id_pseudonyms:
        id_pseudonyms[id_pool_name] = {}

    id_pool = id_pseudonyms[id_pool_name]
    id_prefix = id_change.get('id_prefix', None)
    found = jsonpath_expression.find(resource)
    for match in found:
        path = [str(match.path)]
        match = match.context

        while match.context is not None:
            path = [str(match.path)] + path
            match = match.context

        for index in range(0, len(path) - 1):

            cur_key = path[index]
            if "[" in cur_key:
                cur_key = re.sub(r"[\[\]]", "", cur_key)
                cur_key = int(cur_key)

            resource = resource[cur_key]

        cur_id = resource[path[len(path) - 1]]

        if id_prefix is not None:
            cur_id = cur_id.replace(id_prefix, "")

        if cur_id not in id_pool:
            psd_id = str(uuid.uuid4())
            id_pool[cur_id] = psd_id
        else:
            psd_id = id_pool[cur_id]

        if id_prefix is not None:
            resource[path[len(path) - 1]] = f'{id_prefix}{psd_id}'
        else:
            resource[path[len(path) - 1]] = psd_id


def apply_function_to_field_by_expression(to_apply, resource):

    jsonpath_expression = parse(to_apply['path_to_field'])
    found = jsonpath_expression.find(resource)
    for match in found:
        path = [str(match.path)]
        match = match.context

        while match.context is not None:
            path = [str(match.path)] + path
            match = match.context

        for index in range(0, len(path) - 1):
            cur_key = path[index]
            if "[" in cur_key:
                cur_key = re.sub(r"[\[\]]", "", cur_key)
                cur_key = int(cur_key)
            resource = resource[cur_key]

        cur_field = resource[path[len(path) - 1]]

        resource[path[len(path) - 1]
                 ] = globals()[to_apply['function_to_apply']](cur_field)

def key_is_array_index(key):
    key = str(key)
    if "[" in key:
        return True

    return False

def select_in_obj_by_expression(selection, psd_resource, resource):

    jsonpath_expression = parse(selection)
    found = jsonpath_expression.find(resource)
    for match in found:
        path = [str(match.path)]
        match = match.context

        while match.context is not None:
            path = [str(match.path)] + path
            match = match.context

        for index in range(0, len(path)):
            cur_key = path[index]
            cur_is_array_key = key_is_array_index(cur_key)
            if cur_is_array_key:
                cur_key = re.sub(r"[\[\]]", "", cur_key)
                cur_key = int(cur_key)

            if index == len(path) - 1:

                if cur_is_array_key:
                    psd_resource.append(resource[cur_key])
                else:
                    psd_resource[cur_key] = resource[cur_key]
                continue

            next_key = path[index + 1]
            if cur_key not in psd_resource:
                if key_is_array_index(next_key):
                    psd_resource[cur_key] = []
                elif cur_is_array_key:
                    psd_resource.append({})
                else:
                    psd_resource[cur_key] = {}

            psd_resource = psd_resource[cur_key]
            resource = resource[cur_key]


def pseudonomise_resource(resource, psd_config):

    psd_resource = {}

    for selection in psd_config['select']:
        select_in_obj_by_expression(selection, psd_resource, resource)

    for id_change in psd_config['change_id']:
        change_id_in_obj_by_expression(id_change, psd_resource)

    if 'remove' in psd_config:
        for to_remove in psd_config['remove']:
            remove_from_object_by_expression(to_remove, psd_resource)

    if 'apply_function' in psd_config:
        for to_apply in psd_config['apply_function']:
            apply_function_to_field_by_expression(to_apply, psd_resource)

    print(psd_resource)
    return psd_resource


def pseudonomise_resources(resource_list, psd_config):
    psd_resources = []

    for resource in resource_list:
        psd_resources.append(pseudonomise_resource(resource, psd_config))

    return psd_resources


id_pseudonyms = {}

with open("psd_config.json", 'r') as f:
    psd_configs = json.load(f)

for psd_config in psd_configs:
    input_file = f'{psd_config["input_file_path"]}/{psd_config["psd_name"]}.json'

    with open(input_file, 'r') as f:
        input_list = json.load(f)

    print(f'Begin pseudonymisation of: {input_file}...')
    psd_list = pseudonomise_resources(input_list, psd_config)
    print(f'Finished pseudonymisation of: {input_file}')
    output_file = f'{psd_config["psd_file_path"]}/{psd_config["psd_name"]}_{psd_date_time}.json'
    with open(output_file, 'w') as f:
        json.dump(psd_list, f)

id_psd_file = f'{psd_config["psd_file_path"]}/id_pseudonyms_{psd_date_time}_.json'
with open(id_psd_file, 'w') as f:
    json.dump(id_pseudonyms, f)