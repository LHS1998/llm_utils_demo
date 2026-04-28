import json
from json import load, loads

def dump(obj, f, *args, **kwargs):
    return json.dump(obj, f, ensure_ascii=False, indent=4, *args, **kwargs)

def dumps(obj, *args, **kwargs):
    return json.dumps(obj, ensure_ascii=False, indent=4, *args, **kwargs)
