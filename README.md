# dictselect

A lightweight Python library for extracting data from nested dicts and lists using composable, reusable selectors.

## Installation

```bash
pip install dictselect
```

Requires Python ≥ 3.9.

## Quick start

```python
from dictselect import Selector

data = {
    "image_id": "xa001",
    "annotations": [
        {"id": 1, "x_min": 10, "x_max": 20, "label": "cat"},
        {"id": 2, "x_min": 30, "x_max": 50, "label": "dog"},
    ],
}

Selector["image_id"](data)                          # → "xa001"
Selector["annotations"][0]["label"](data)           # → "cat"
Selector["annotations"][:]["label"](data)           # → ["cat", "dog"]
Selector["annotations"][:]["x_min", "x_max"](data)  # → [[10, 20], [30, 50]]
```

Build a selector once, apply it to many objects:

```python
sel = Selector["annotations"][:]["x_min", "x_max"]
sel(record_a)
sel(record_b)
```

## Operations

| Syntax                               | What it does                                        |
|--------------------------------------|-----------------------------------------------------|
| `Selector["key"]`                    | Dict key or list index lookup                       |
| `Selector[0]`, `Selector[-1]`        | List index (positive or negative)                   |
| `Selector[1:3]`                      | Slice — returns a sub-list or sub-string            |
| `Selector[:]` or `Selector[...]`     | Fan-out — map remaining steps over every element    |
| `Selector["a", "b"]`                 | Pluck multiple keys at once, returns a list         |
| `Selector.attr`                      | Attribute access (`getattr`)                        |
| `Selector.method(args)`              | Attribute access followed by a call                 |
| `sel_a + sel_b`                      | Compose two selectors                               |
| `sel(data, include_keys=True)`       | Wrap result in a dict keyed by the last access key  |
| `sel(data, include_null=True)`       | Return `None` instead of raising on missing keys    |
| `Selector[{"alias": "key"}]`         | Aliased key — access via `"key"`, label as `"alias"`|
| `Selector["fn"].invoke(*args)`       | Call a callable value stored in data                |

## Usage

### Key and index lookup

```python
Selector["name"]({"name": "Alice"})   # → "Alice"
Selector[0]([10, 20, 30])             # → 10
Selector[-1]([10, 20, 30])            # → 30
Selector["a"]["b"]({"a": {"b": 7}})  # → 7
```

### Slicing

```python
Selector[1:3]([0, 1, 2, 3, 4])  # → [1, 2]
Selector[:2]([10, 20, 30])       # → [10, 20]
Selector[-2:]([10, 20, 30])      # → [20, 30]
Selector[::2]([0, 1, 2, 3, 4])  # → [0, 2, 4]
```

### Fan-out `[:]`

`[:]` (or `[...]`) maps all subsequent steps over every element of the current sequence. Steps after `[:]` run on each element individually.

```python
data = [{"v": 1}, {"v": 2}, {"v": 3}]

Selector[:]["v"](data)   # → [1, 2, 3]
Selector[:][0]([[10, 20], [30, 40]])  # → [10, 30]
```

### Plucking multiple keys

Pass a tuple or list of keys to retrieve several fields at once. All keys must be the same type (all `str` or all `int`). Returns a list of values in the order given.

```python
Selector["x", "y"]({"x": 1, "y": 2, "z": 3})  # → [1, 2]
Selector[0, 2]([10, 20, 30, 40])               # → [10, 30]
```

Combined with fan-out:

```python
Selector["annotations"][:]["x_min", "x_max"](data)
# → [[10, 20], [30, 50]]
```

### Attribute access and method calls

Chain attribute access with `.attr`, then call it like a regular Python method:

```python
Selector.upper()("hello")                   # → "HELLO"
Selector.replace("l", "r")("hello")        # → "herro"
Selector[:].upper()(["hi", "there"])       # → ["HI", "THERE"]
Selector["title"].upper()({"title": "hi"}) # → "HI"
```

### Composing selectors

Join two selectors with `+`. Neither operand is mutated:

```python
head = Selector["data"][:]
tail = Selector["value"]
sel = head + tail
sel({"data": [{"value": 1}, {"value": 2}]})  # → [1, 2]
```

### Calling vs. evaluating

Normally, calling a selector evaluates it against the data:

```python
sel = Selector["key"]
sel({"key": 42})       # → 42
sel.apply({"key": 42}) # same thing
```

**Attribute-access exception:** if the last recorded step is an attribute name, calling the selector *records* a method-call step instead of evaluating. Use `.apply()` to force evaluation:

```python
Selector["title"].upper()           # records the .upper() call — returns a new Selector
Selector["title"].upper()(data)     # evaluates → "HELLO"

Selector.upper.apply("hello")       # force-evaluates → the bound method object (not "HELLO")
```

**Calling a function stored in data:** accessing a callable value via `["key"]` and then calling with `()` would evaluate the selector (returning the function itself), not invoke it. Use `.invoke()` to record a function call as a step:

```python
data = {"fn": lambda x: x * 2}

Selector["fn"](data)            # → the lambda object (selector evaluated, function not called)
Selector["fn"].invoke(21)(data) # → 42 (function is called with 21 at evaluation time)
```

## Returning keys alongside values

Pass `include_keys=True` to wrap the result in a dict keyed by the last access key.

```python
Selector["a"]["b"]({"a": {"b": 12}}, include_keys=True)
# → {"b": 12}

Selector["x"].apply({"x": 7}, include_keys=True)
# → {"x": 7}
```

With fan-out, wrapping happens per element:

```python
Selector[:]["a"]([{"a": 1}, {"a": 2}], include_keys=True)
# → [{"a": 1}, {"a": 2}]

Selector[:]["a", "b"]([{"a": 1, "b": 2, "c": 3}, {"a": 4, "c": 6, "b": 5}], include_keys=True)
# → [{"a": 1, "b": 2}, {"a": 4, "b": 5}]
```

Terminal steps that are not key lookups (slices, method calls) pass through unchanged.

### Aliasing output keys

Use a single-entry dict `{"alias": "key"}` to rename a field in the output. The dict key is the **output name**, the dict value is the **access key**. Plain keys keep their original name.

```python
Selector[{"alias_a": "a"}]({"a": 7}, include_keys=True)
# → {"alias_a": 7}

Selector[{"alias_a": "a"}, "b", {"alias_c": "c"}](
    {"a": 1, "b": 2, "c": 3}, include_keys=True
)
# → {"alias_a": 1, "b": 2, "alias_c": 3}
```

Without `include_keys`, aliases are ignored and raw values are returned as usual.

### Sub-selector aliases

The access value in an alias dict can itself be a `Selector`. It is applied to the current data and stored under the given alias. A bare `Selector` without an alias is not allowed.

```python
name_sel = Selector["name"]["first_name", "last_name"]

Selector["employees"][:][{"name": name_sel}, "adress"](data, include_keys=True)
# → [
#     {"name": ["Alice", "Smith"], "adress": "1 Main St"},
#     {"name": ["Bob",   "Jones"], "adress": "2 Oak Ave"},
# ]
```

## Handling missing values

Pass `include_null=True` to return `None` instead of raising `KeyError` or `IndexError` when a key or index is absent. Once a step fails, the rest of the chain is skipped.

```python
Selector["a"]["missing"]({"a": {}}, include_null=True)
# → None

Selector[:]["x"]([{"x": 1}, {"y": 2}, {"x": 3}], include_null=True)
# → [1, None, 3]

Selector["a", "b"]({"a": 1}, include_null=True)
# → [1, None]  (each missing key becomes None individually)
```

Both flags can be combined:

```python
Selector[:]["x"]([{"x": 1}, {"y": 2}], include_null=True, include_keys=True)
# → [{"x": 1}, {"x": None}]
```
