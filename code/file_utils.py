import os
import json
from dot_dict import convert_to_dot_dict
from smart_json_dump import smart_json_dump


def get_base_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def load_text(dirname, filename=None):
    base_dir = get_base_dir()

    if filename:
        return convert_to_dot_dict(json.load(open(f'{base_dir}/{dirname}/{filename}.json')))
    final_data = None
    for filename in sorted(os.listdir(f'{base_dir}/{dirname}')):
        if not filename.endswith("json"):
            continue            
        data = convert_to_dot_dict(json.load(open(f'{base_dir}/{dirname}/{filename}')))
        if not final_data:
            final_data = data
        else:
            final_data.data.extend(data.data)
    return final_data


def write_text(data, name):
    base_dir = get_base_dir()
    smart_json_dump(data, f'{base_dir}/{name}/{name}.json')
