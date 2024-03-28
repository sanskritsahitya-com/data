"""
JSON files in this repo have been pretty-printed using the custom method given below.
Simply call smart_json_dump with the final dict object representing the overall JSON.

Most notably this format ensures that each list entry inside a top level key comes on a new line. 

This way, each shloka inside data gets a new line and it's easier to see the structure of the file and ensures clean diffs.
"""

import json


def smart_json_string(data):
    final_string = []
    encoder = json.JSONEncoder(ensure_ascii=False)
    for key, value in data.items():
        sub_str = ""
        if type(value) == list:
            sub_str += f"{encoder.encode(key)}: [\n"
            sub_str += ",\n".join([json.dumps(v, ensure_ascii=False) for v in value])
            sub_str += "]"
        else:
            sub_str += f"{encoder.encode(key)}: {encoder.encode(value)}"
        final_string.append(sub_str)
    return "{\n" + ",\n".join(final_string) + "\n}"


def smart_json_dump(data, filename):
    open(filename, "w").write(smart_json_string(data))
