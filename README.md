# dictselect

A Python library for extracting data from nested dicts and lists using reusable pipelines.

```python
from dictselect import Selector

pipe = Selector["annotations"][:]["x_min", "x_max"]
my_data_selection = pipe(data_dict)
```

## Installation

```bash
pip install dictselect
```

Requires Python ≥ 3.9.

## How it works

Build a `Selector` by chaining operations, then call it with your data. The pipeline is built to be reusable.

```python
from dictselect import Selector

data_dict = {
    "image_id": "xa001",
    "annotations": [
        {"id": 1, "x_min": 10, "x_max": 20, "label": "cat"},
        {"id": 2, "x_min": 30, "x_max": 50, "label": "dog"},
    ],
}

Selector["image_id"](data_dict)                          # → "xa001"
Selector["annotations"][0]["label"](data_dict)           # → "cat"
Selector["annotations"][:]["label"](data_dict)           # → ["cat", "dog"]
Selector["annotations"][:]["x_min", "x_max"](data_dict)  # → [[10, 20], [30, 50]]
```

## Operations

| Syntax                             | What it does                                                            |
|------------------------------------|-------------------------------------------------------------------------|
| `Selector["key"]`                  | Dict key or list index lookup                                           |
| `Selector[0]`, `Selector[-1]`      | List index                                                              |
| `Selector[1:3]`                    | Slice                                                                   |
| `Selector[:]` or `Selector[...]`   | Fan-out — apply the rest of the chain to **every element** at this step |
| `Selector["a", "b"]`               | Input multiple keys at once, returns a list                             |
| `Selector.method()`                | Call a method on the current value                                      |
| `pipe_a + pipe_b`                  | Compose two pipelines into one                                          |
| `Selector.invoke(*args, **kwargs)` | Call the function if the current value is a function                    |

### Fan-out `[:]`

`[:]` maps the remaining steps over every item in this step. Steps after `[:]` run on each element individually.

```python
data = [{"v": 1}, {"v": 2}, {"v": 3}]

Selector[:]["v"](data)   # → [1, 2, 3]
Selector[:][:][0]([[10, 20], [30, 40]])  # → [[10], [30]]  (nested fan-out)
```

### Multi-key input `["a", "b"]`

Returns a list of values for each key. All keys must be the same type (all strings or all integers).

```python
Selector["x", "y"]({"x": 1, "y": 2, "z": 3})  # → [1, 2]
```

### Method calls

Access an attribute, then call it like a regular Python method.

```python
Selector.upper()("hello")               # → "HELLO"
Selector[:].upper()(["hi", "there"])    # → ["HI", "THERE"]
```

### Composition

Join two pipelines with `+`.

```python
head = Selector["data"][:]
tail = Selector["value"]
(head + tail)({"data": [{"value": 1}, {"value": 2}]})  # → [1, 2]
```

## Including keys in the result

Pass `include_keys=True` to wrap the result with the last key as a dict. Works for single key lookups and multi-key inputs.

```python
Selector["a"]["b"]({"a": {"b": 12}}, include_keys=True)
# → {"b": 12}

Selector[:]["a"]([{"a": 1}, {"a": 2}], include_keys=True)
# → [{"a": 1}, {"a": 2}]

Selector[:]["a", "b"]([{"a": 1, "b": 2, "c": 3}, {"a": 4, "c": 6, "b": 5}], include_keys=True)
# → [{"a": 1, "b": 2}, {"a": 4, "b": 5}]
```

Also works on `.apply()`:

```python
Selector["x"].apply({"x": 7}, include_keys=True)  # → {"x": 7}
```

### Aliasing output keys

Use a single-entry dict `{"key": "alias"}` instead of a plain key to rename the output field. Plain keys keep their original name. This works for single lookups and multi-key inputs alike.

```python
Selector[{"a": "alias_a"}]({"a": 7}, include_keys=True)
# → {"alias_a": 7}

Selector[{"a": "alias_a"}, "b", {"c": "alias_c"}](
    {"a": 1, "b": 2, "c": 3}, include_keys=True
)
# → {"alias_a": 1, "b": 2, "alias_c": 3}
```

Without `include_keys`, aliases are ignored and raw values are returned as usual.

## Handling missing values

Pass `include_null=True` to get `None` instead of a `KeyError`/`IndexError` when a key or index doesn't exist. Once a step fails, the rest of the chain is skipped and `None` is returned.

```python
Selector["a"]["missing"]({"a": {}}, include_null=True)
# → None   (instead of KeyError)

Selector[:]["x"]([{"x": 1}, {"y": 2}, {"x": 3}], include_null=True)
# → [1, None, 3]

Selector["a", "b"]({"a": 1}, include_null=True)
# → [1, None]   (missing keys in multi-select become None individually)
```

The two flags can be combined:

```python
Selector[:]["x"]([{"x": 1}, {"y": 2}], include_null=True, include_keys=True)
# → [{"x": 1}, {"x": None}]
```

## Calling vs. evaluating

Normally, calling a selector evaluates it:

```python
pipe = Selector["key"]
pipe({"key": 42})  # → 42
```

**Exception 1:** if the last step is an attribute name (e.g. `.upper`), calling it *records* a method call instead of evaluating. Use `.apply(data)` to force evaluation in that case.

```python
pipe = Selector["title"].upper()       # records .upper() call
pipe({"title": "hello"})               # evaluates → "HELLO"

Selector.upper.apply("hello")          # force evaluation → <method object>
```

**Exception 2:** if the last step is a function as a value, use `.invoke(*args, **kwargs)` to force evaluation in that case.

```python
pipe = Selector["function"]()            # value will be a function. Calling the function, results in evaluating the selector -> ERROR.
pipe = Selector["function"].invoke()     # Calls the function without evaluating the Selector
```
