from typing import Any


class Selector:
    """
    Selector for nested data and dynamic attribute/method access.
    """

    def __init__(self, steps=None):
        self.steps = steps or []

    def __getitem__(self, key):
        if key in (slice(None), Ellipsis):
            return Selector(self.steps + [("map", Ellipsis)])
        type_ = "slice" if isinstance(key, slice) else "getitem"
        return Selector(self.steps + [(type_, key)])

    def __getattr__(self, name):
        return Selector(self.steps + [("getattr", name)])

    def __call__(self, *args, **kwargs):
        return Selector(self.steps + [("call", args, kwargs)])

    def __repr__(self):
        return f"Selector({self.steps})"

    def __add__(self, other):
        if not isinstance(other, Selector):
            raise ValueError(f"Invalid attribute for __add__: {type(other).__name__}")
        self.steps.extend(other.steps)
        return self

    def apply(self, data: Any):
        for type_, *payload in self.steps:
            match type_:
                case "map":
                    data = [self.__class__(self.steps[self.steps.index((type_, *payload))+1:]).apply(x) for x in data]
                    break
                case "slice":
                    data = data[payload[0]]
                case "getitem":
                    key = payload[0]
                    if isinstance(key, list):
                        if all(isinstance(k, int) for k in key) or all(isinstance(k, str) for k in key):
                            data = [data[k] for k in key]
                        else:
                            raise TypeError(f"Invalid key list for {type(data).__name__}")
                    else:
                        data = data[key]
                case "getattr":
                    data = getattr(data, payload[0])
                case "call":
                    args, kwargs = payload
                    data = data(*args, **kwargs)
        return data

















# if __name__ == "__main__":
#     item = {
#         "annotations": [
#             {"id": 0, "x_min": 1, "y_min": 1, "x_max": 2, "y_max": 2, "label": "car"},
#             {"id": 0, "x_min": 1, "y_min": 3, "x_max": 2, "y_max": 5, "label": "car"},
#             {"id": 0, "x_min": 1, "y_min": 1, "x_max": 3, "y_max": 2, "label": "other"},
#             {"id": 0, "x_min": 1, "y_min": 1, "x_max": 2, "y_max": 3, "label": "truck"},
#         ],
#         "image_id": "xa001",
#     }
#
#     S = Selector()
#     annots = S["annotations"][:]["x_min", "x_max", "y_min", "y_max"]
#     new_annots = S["annotations"][:]["id"].conjugate()
#     print(new_annots(item))
