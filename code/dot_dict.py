"""A utility module to provide dot-notation access to dictionaries."""


class DotDict(dict):
    """A dictionary subclass that allows dot-notation access (e.g., dict.key)."""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def convert_to_dot_dict(input_data):
    """Recursively converts dictionaries in the input to DotDict objects.

    Args:
        input_data: The data to convert. Can be a dict, list, or primitive.

    Returns:
        The converted data with DotDicts where dicts were present.
    """
    if isinstance(input_data, dict):
        out = DotDict()
        for key, value in input_data.items():
            out[key] = convert_to_dot_dict(value)
        return out
    if isinstance(input_data, list):
        return list(map(convert_to_dot_dict, input_data))
    return input_data
