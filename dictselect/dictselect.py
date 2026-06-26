"""dictselect — a tiny lazy selector for nested Python data structures.

Build a reusable pipeline of access operations (key lookup, slicing, attribute
access, method calls) and apply it to any compatible data object.

Example::

    from dictselect import Selector

    # Build a pipeline once.
    pipe = Selector["annotations"][:]["x_min", "x_max", "y_min", "y_max"]

    # Apply it to multiple data objects.
    result = pipe(record)
    # → [[x_min, x_max, y_min, y_max], ...] for every "annotation" in record

Supported operations
--------------------
* Selector["key"]                   — dict / sequence key lookup
* Selector[1:3]                     — slice
* Selector[:] or Selector[...]      — fan-out over a sequence (map)
* Selector["a", "b"]                — pluck multiple str (or int) keys at once
* Selector.attr                     — attribute access
* Selector.method(args)             — record a method call (chained after attr access)
* pipe_a + pipe_b                   — compose two pipelines
* pipe(data) or pipe.apply(data)    — evaluate a pipeline against data
* pipe(data, include_keys=True)     — wrap leaf result(s) with the last key as a dict
* Selector[{"alias": "key"}]        — aliased key: lookup uses "key", wrap uses "alias"
* Selector[{"x": "a"}, "b"]        — mixed multi-key: aliases per item, plain keys fall back to their name
* Selector[{"name": sub_selector}] — sub-selector alias: sub_selector is applied to the current data,
                                     stored under "name" (only effective with include_keys=True)
* pipe(data, include_null=True)     — return None for missing keys instead of raising

Python ≥ 3.9 is required.
"""

from __future__ import annotations

from typing import Any

__all__ = ["Selector"]
__version__ = "0.1.0"

_MISSING = object()  # sentinel for a failed retrieval when include_null=True


class _SelectorMeta(type):
    @property
    def steps(cls):
        return ()

    def __getattr__(cls, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return cls((("getattr", name),))


class Selector(metaclass=_SelectorMeta):
    """An immutable, composable pipeline of data-access operations.

    A Selector accumulates a sequence of steps (key lookups, slices,
    attribute accesses, …) and evaluates them lazily when .apply() is
    called (or equivalently when the instance is called like a function).

    Build selectors by subscripting the class or an existing instance:

        pipe = Selector["annotations"][:]["label"]
        labels = pipe(record)          # evaluate
        labels = pipe.apply(record)    # same thing

    Evaluation rule for pipe(data)

    Calling an instance normally evaluates the pipeline.  The one exception:
    if the last recorded step is an attribute lookup (e.g. the chain ends with
    .upper), the call is interpreted as a method-call step and returns a
    new Selector—mirroring how Python itself handles obj.method(args):

        text_pipe = Selector["title"].upper()   # records .upper() call
        result = text_pipe({"title": "hello"})  # → "HELLO"

    To always force a call step regardless of the preceding step, use
    .invoke():

        fn_pipe = Selector["callback"].invoke(42)
        fn_pipe({"callback": lambda x: x * 2})  # → 84

    Composition

    Two selectors can be joined with +; neither operand is mutated:

        head = Selector["data"][:]
        tail = Selector["value"]
        pipe = head + tail           # equivalent to Selector["data"][:]["value"]

    Immutability

    Every builder method (__getitem__, __getattr__, __call__, …)
    returns a new Selector; the original is never modified.  Steps are
    stored as a plain tuple so they are cheaply shareable.
    """

    __slots__ = ("steps",)

    def __init__(self, steps: tuple = ()):
        """Initialize a selector with the given steps.

        Args:
            steps:
                Sequence of step tuples that form the pipeline.  Pass nothing (or
                an empty tuple) to create the identity/root selector.

        Example:
            empty = Selector()           # identity — apply returns data unchanged
            copy  = Selector(other.steps)  # clone
        """
        self.steps = tuple(steps)

    @classmethod
    def __class_getitem__(cls, key):
        """Allow Selector[key] as a shorthand for Selector()[key].

        This lets you start a chain without an explicit Selector() call:

            pipe = Selector["annotations"][:]["id"]

        Args:
            key:
                The first access step; forwarded to __getitem__.

        Returns:
            Selector: A new selector with the first step recorded.
        """
        return cls()[key]

    def __getitem__(self, key):
        """Record a key-access, slice, fan-out, or multi-key pluck step.

        Behavior depends on key:

        * [:] | [...]
              Fan-out (map): apply all remaining steps to every element of the
              current sequence and return a list of results.
        * [a:b] / [a:b:c]
              Arbitrary slice; applied directly to the current data.
        * ["a", "b"] | [["a", "b"]]
              Multi-key pluck: all keys must be the same type (all str or
              all int).  Returns a list of the selected values.
        * Any other value
              Plain key / index lookup (data[key]).

        Args:
            key:
                The subscript expression.

        Returns:
            Selector: A new selector with the step appended.

        Raises:
            TypeError: If key is a tuple or list with mixed str/int types, or
                       with fewer than 2 elements.

        Example:
            Selector["name"].apply({"name": "Alice"})          # → "Alice"
            Selector[0].apply([10, 20, 30])                    # → 10
            Selector[1:3].apply([0, 1, 2, 3])                  # → [1, 2]
            Selector["x", "y"].apply({"x": 1, "y": 2, "z": 3}) # → [1, 2]
            Selector[:]["x"].apply([{"x": 1}, {"x": 2}])       # → [1, 2]
        """
        if key is Ellipsis or (isinstance(key, slice) and key == slice(None)):
            return type(self)(self.steps + (("map",),))
        if isinstance(key, slice):
            return type(self)(self.steps + (("slice", key),))
        if isinstance(key, dict):
            if len(key) != 1:
                raise TypeError(
                    f"Aliased key lookup requires a single-entry dict; "
                    f"got {len(key)} entries."
                )
            (alias, access_key), = key.items()  # {alias: access_key}
            return type(self)(self.steps + (("getitem", access_key, alias),))
        if isinstance(key, (tuple, list)):
            if len(key) < 2:
                raise TypeError(
                    "Multi-key selection requires at least 2 keys; "
                    f"got {len(key)}."
                )
            access_keys = []
            aliases = []
            any_alias = False
            for item in key:
                if isinstance(item, dict):
                    if len(item) != 1:
                        raise TypeError(
                            f"Aliased key lookup requires a single-entry dict; "
                            f"got {len(item)} entries."
                        )
                    (a, k), = item.items()  # {alias: access_key}
                    access_keys.append(k)
                    aliases.append(a)
                    any_alias = True
                elif isinstance(item, Selector):
                    raise TypeError(
                        "A Selector access must be aliased; "
                        "use {'name': selector} instead of a bare Selector."
                    )
                else:
                    access_keys.append(item)
                    aliases.append(None)
            # Selectors are exempt from the homogeneity check; only plain keys must agree
            plain_keys = [k for k in access_keys if not isinstance(k, Selector)]
            if all(isinstance(k, str) for k in plain_keys):
                pass
            elif all(isinstance(k, int) for k in plain_keys):
                pass
            else:
                raise TypeError(
                    "Multi-key selection requires homogeneous keys "
                    "(all str or all int); got mixed types."
                )
            if any_alias:
                return type(self)(self.steps + (("multi", tuple(access_keys), tuple(aliases)),))
            return type(self)(self.steps + (("multi", tuple(access_keys)),))
        if isinstance(key, Selector):
            raise TypeError(
                "A Selector access must be aliased; "
                "use {'name': selector} instead of a bare Selector."
            )
        return type(self)(self.steps + (("getitem", key),))

    def __getattr__(self, name: str):
        """Record an attribute-access step.

        Args:
            name:
                The attribute name.

        Returns:
            Selector: A new selector with the step appended.

        Raises:
            AttributeError: Immediately for any dunder name (__copy__, __reduce__, …)
                            so that pickle, copy, and introspection tools behave correctly.

        Example:
            Selector.upper.apply("hello")          # → <method 'upper'>
            Selector.upper().apply("hello")        # → "HELLO"
        """
        if name.startswith("__"):
            raise AttributeError(name)
        return type(self)(self.steps + (("getattr", name),))

    def __call__(self, *args, **kwargs):
        """Evaluate the pipeline or record a method-call step.

        Evaluation

        When the last step is not an attribute lookup—or when there are no
        steps—calling the selector evaluates it against the single positional
        argument:

            pipe = Selector["key"]
            pipe({"key": 42})   # → 42

        Method-call recording (the special case)

        When the last step *is* an attribute lookup (e.g. the chain ends with
        .upper), the call mirrors Python's own obj.attr(args) pattern
        and records a call step instead of evaluating:

            pipe = Selector.upper()            # records .upper() call
            pipe("hello")                      # evaluates → "HELLO"

        To always record a call step (bypassing the heuristic), use
        .invoke().

        Args:
            *args, **kwargs: For evaluation: exactly one positional argument (the data).
                             For recording: any arguments forwarded to the method call.

        Returns:
            Any | Selector: The result of apply(data) when evaluating, or a new
                            Selector with the call step appended when recording.

        Raises:
            TypeError: If the heuristic selects *evaluation* but the wrong number of
                       arguments are supplied.
        """
        if self.steps and self.steps[-1][0] == "getattr":
            return type(self)(self.steps + (("call", args, kwargs),))
        extra = set(kwargs) - {"include_keys", "include_null"}
        if len(args) != 1 or extra:
            raise TypeError(
                "Selector evaluation expects exactly one positional argument "
                "(the data) and optional include_keys / include_null keywords. "
                "To record a method call, access the method via attribute first "
                "(e.g. pipe.method(args)), or use "
                "pipe.invoke(args) to record a call step explicitly."
            )
        return self.apply(args[0], **kwargs)

    def invoke(self, *args, **kwargs):
        """Record a call step unconditionally, regardless of the previous step.

        Use this when you need to invoke a callable obtained via key lookup
        (not attribute access), where the default __call__ heuristic would
        interpret the call as an evaluation instead:

            pipe = Selector["handler"].invoke(event)
            pipe({"handler": lambda e: e.upper()})  # → "EVENT" (if event="event")

        Args:
            *args, **kwargs: Arguments that will be forwarded to the callable at evaluation time.

        Returns:
            Selector: A new selector with the call step appended.
        """
        return type(self)(self.steps + (("call", args, kwargs),))

    def __add__(self, other):
        """Return a new selector that concatenates the steps of both operands.

        Neither self nor other is mutated:

            head = Selector["data"][:]
            tail = Selector["value"]
            pipe = head + tail      # Selector["data"][:]["value"]

        Args:
            other: Another Selector instance.

        Returns:
            Selector: A fresh selector whose steps are ``self.steps + other.steps``.

        Raises:
            TypeError: If other is not a Selector instance (via NotImplemented
                       so Python can try other.__radd__).
        """
        if other is type(self):
            return type(self)(self.steps)
        if not isinstance(other, type(self)):
            return NotImplemented
        return type(self)(self.steps + other.steps)

    def __repr__(self):
        """Return a developer-friendly representation listing all steps.

        Example:
            repr(Selector["a"][:])  # → "Selector([('getitem', 'a'), ('map',)])"
        """
        return f"Selector({list(self.steps)!r})"

    @staticmethod
    def __apply_map(data, rest_steps, include_keys, include_null):
        if not rest_steps:
            return list(data)
        rest = Selector(rest_steps)
        return [
            rest.apply(x, include_keys=include_keys, include_null=include_null)
            for x in data
        ]

    @staticmethod
    def __execute_step(data, step, include_null):
        kind = step[0]
        try:
            if kind == "getitem":
                access = step[1]
                if isinstance(access, Selector):
                    return access.apply(data, include_null=include_null)
                return data[access]
            if kind == "slice":
                return data[step[1]]
            if kind == "multi":
                def _resolve(k):
                    if isinstance(k, Selector):
                        return k.apply(data, include_null=include_null)
                    return data[k]
                if include_null:
                    row = []
                    for k in step[1]:
                        try:
                            row.append(_resolve(k))
                        except (KeyError, IndexError, TypeError):
                            row.append(None)
                    return row
                return [_resolve(k) for k in step[1]]
            if kind == "getattr":
                return getattr(data, step[1])
            if kind == "call":
                _, call_args, call_kwargs = step
                return data(*call_args, **call_kwargs)
        except (KeyError, IndexError, AttributeError, TypeError):
            if include_null:
                return _MISSING
            raise
        return data  # unreachable; unknown step kind leaves data unchanged

    @staticmethod
    def __wrap_keys(data, last_step):
        if last_step[0] == "getitem":
            alias = last_step[2] if len(last_step) > 2 else None
            name = alias if alias is not None else last_step[1]
            return {name: data}
        if last_step[0] == "multi":
            keys = last_step[1]
            aliases = last_step[2] if len(last_step) > 2 else (None,) * len(keys)
            names = [a if a is not None else k for k, a in zip(keys, aliases)]
            return dict(zip(names, data))
        return data

    def apply(self, data: Any, include_keys: bool = False, include_null: bool = False) -> Any:
        """Evaluate the recorded pipeline against data.

        Steps are executed in order:

        * getitem — data[key]
        * slice   — data[slice]
        * multi   — [data[k] for k in keys]
        * map     — apply remaining steps to every element; returns a list
        * getattr — getattr(data, name)
        * call    — data(*args, **kwargs)

        A selector with no steps is the identity: it returns *data* unchanged.

        Args:
            data: The root data object to query.
            include_keys: If True, wrap the leaf result with the last key-bearing
                step's key(s) as a dict.  Only ``getitem`` and ``multi`` steps
                qualify; all other terminal steps leave the result unchanged.

                Selector["b"].apply({"b": 7}, include_keys=True)          # → {"b": 7}
                Selector["a","b"].apply({"a":1,"b":2}, include_keys=True)  # → {"a":1,"b":2}

                With a fan-out (``[:]``), the wrapping happens per element:
                Selector[:]["v"].apply([{"v":1},{"v":2}], include_keys=True)
                # → [{"v": 1}, {"v": 2}]

            include_null: If True, return None (instead of raising) when a key,
                index, or attribute is missing.  The None propagates through the
                rest of the chain so subsequent steps are skipped.

                For multi select, each missing key becomes None individually:
                Selector["a","b"].apply({"a": 1}, include_null=True)  # → [1, None]

                With a fan-out, missing elements become None per item:
                Selector[:]["x"].apply([{"x":1},{"y":2}], include_null=True)
                # → [1, None]

        Returns:
            Any: The result after all steps have been applied.

        Example:
            Selector["a"]["b"].apply({"a": {"b": 7}})  # → 7
            Selector[:]["v"].apply([{"v": 1}, {"v": 2}])  # → [1, 2]
        """
        for i, step in enumerate(self.steps):
            if step[0] == "map":
                return self.__apply_map(data, self.steps[i + 1:], include_keys, include_null)

            # Short-circuit: a previous step already failed
            if include_null and data is _MISSING:
                continue

            data = self.__execute_step(data, step, include_null)

        if include_null and data is _MISSING:
            data = None

        if include_keys and self.steps:
            return self.__wrap_keys(data, self.steps[-1])
        return data
