"""Tests for dictselect.Selector."""

import pickle

import pytest

from dictselect import Selector


RECORD = {
    "annotations": [
        {"id": 0, "x_min": 1, "y_min": 1, "x_max": 2, "y_max": 2, "label": "car"},
        {"id": 0, "x_min": 1, "y_min": 3, "x_max": 2, "y_max": 5, "label": "car"},
        {"id": 0, "x_min": 1, "y_min": 1, "x_max": 3, "y_max": 2, "label": "other"},
        {"id": 0, "x_min": 1, "y_min": 1, "x_max": 2, "y_max": 3, "label": "truck"},
    ],
    "image_id": "xa001",
}


class TestGetitem:
    def test_dict_str_key(self):
        assert Selector["image_id"].apply(RECORD) == "xa001"

    def test_list_int_index(self):
        assert Selector[0].apply([10, 20, 30]) == 10

    def test_negative_index(self):
        assert Selector[-1].apply([10, 20, 30]) == 30

    def test_chained_dict_access(self):
        data = {"a": {"b": {"c": 42}}}
        assert Selector["a"]["b"]["c"].apply(data) == 42

    def test_chained_list_and_dict(self):
        data = [{"x": 7}]
        assert Selector[0]["x"].apply(data) == 7

    def test_class_subscript_entry_point(self):
        assert Selector["image_id"].apply(RECORD) == Selector()["image_id"].apply(RECORD)

    def test_eval_via_call(self):
        assert Selector["image_id"](RECORD) == "xa001"

    def test_eval_and_apply_agree(self):
        pipe = Selector["image_id"]
        assert pipe(RECORD) == pipe.apply(RECORD)


class TestSlice:
    def test_range_slice(self):
        assert Selector[1:3].apply([0, 1, 2, 3, 4]) == [1, 2]

    def test_head_slice(self):
        assert Selector[:2].apply([10, 20, 30]) == [10, 20]

    def test_tail_slice(self):
        assert Selector[-2:].apply([10, 20, 30]) == [20, 30]

    def test_step_slice(self):
        assert Selector[::2].apply([0, 1, 2, 3, 4]) == [0, 2, 4]

    def test_partial_slice_on_string(self):
        assert Selector[1:4].apply("hello") == "ell"


class TestMap:
    def test_full_slice_fans_out(self):
        """S[:] on a list returns a copy of that list (identity fan-out)."""
        assert Selector[:].apply([1, 2, 3]) == [1, 2, 3]

    def test_ellipsis_fans_out(self):
        assert Selector[...].apply([1, 2, 3]) == [1, 2, 3]

    def test_colon_and_ellipsis_equivalent(self):
        data = [{"x": 1}, {"x": 2}]
        assert Selector[:]["x"].apply(data) == Selector[...]["x"].apply(data)

    def test_map_then_getitem(self):
        data = [{"x": 1}, {"x": 2}, {"x": 3}]
        assert Selector[:]["x"].apply(data) == [1, 2, 3]

    def test_map_empty_sequence(self):
        assert Selector[:]["x"].apply([]) == []

    # Regression – bug #3: duplicate map steps used to pick the wrong remainder
    def test_nested_map_no_index_collision(self):
        data = [[1, 2], [3, 4]]
        assert Selector[:][:].apply(data) == [[1, 2], [3, 4]]

    def test_triple_nested_map(self):
        data = [[[1, 2], [3]], [[4]]]
        assert Selector[:][:][:].apply(data) == [[[1, 2], [3]], [[4]]]

    def test_map_then_attr_and_call(self):
        assert Selector[:].upper().apply(["hello", "world"]) == ["HELLO", "WORLD"]


class TestMultiKey:
    # Regression – bug #2: original code only checked for list, not tuple
    def test_tuple_syntax_str_keys(self):
        data = {"a": 1, "b": 2, "c": 3}
        assert Selector["a", "b"].apply(data) == [1, 2]

    def test_list_syntax_str_keys(self):
        data = {"a": 1, "b": 2, "c": 3}
        assert Selector[["a", "b"]].apply(data) == [1, 2]

    def test_tuple_syntax_int_keys(self):
        assert Selector[0, 2].apply([10, 20, 30, 40]) == [10, 30]

    def test_list_syntax_int_keys(self):
        assert Selector[[0, 2]].apply([10, 20, 30, 40]) == [10, 30]

    def test_mixed_key_types_raise(self):
        with pytest.raises(TypeError, match="homogeneous"):
            Selector["a", 1]

    def test_single_element_multi_key_raises(self):
        with pytest.raises(TypeError, match="at least 2"):
            Selector[["only_one"]]

    def test_map_then_multi_key_str(self):
        """Primary use-case: pluck multiple fields from each element."""
        result = Selector["annotations"][:]["x_min", "x_max", "y_min", "y_max"].apply(RECORD)
        assert result == [
            [1, 2, 1, 2],
            [1, 2, 3, 5],
            [1, 3, 1, 2],
            [1, 2, 1, 3],
        ]


class TestGetattr:
    def test_simple_attribute(self):
        class Obj:
            value = 99
        assert Selector.value.apply(Obj()) == 99

    def test_chained_attributes(self):
        class Inner:
            x = 5
        class Outer:
            inner = Inner()
        assert Selector.inner.x.apply(Outer()) == 5

    def test_dunder_attr_raises_attribute_error(self):
        with pytest.raises(AttributeError):
            _ = Selector["x"].__copy__

    def test_hasattr_dunder_is_false(self):
        assert not hasattr(Selector["x"], "__copy__")


class TestMethodChain:
    def test_call_after_getattr_records_step(self):
        """Calling a selector whose last step is getattr records a call step."""
        pipe = Selector.upper()
        assert pipe.steps == (("getattr", "upper"), ("call", (), {}))

    def test_str_upper_method_chain(self):
        assert Selector.upper().apply("hello") == "HELLO"

    def test_method_with_args(self):
        assert Selector.replace("l", "y").apply("hello") == "heyyo"

    def test_method_with_positional_args(self):
        # str.center takes fillchar as positional-only in CPython
        result = Selector.center(7, "-").apply("hi")
        assert len(result) == 7 and result.strip("-") == "hi"

    def test_chained_method_after_getitem(self):
        assert Selector["title"].upper().apply({"title": "hello"}) == "HELLO"

    def test_annotation_conjugate_pipeline(self):
        pipe = Selector["annotations"][:]["id"].conjugate()
        assert pipe.apply(RECORD) == [0, 0, 0, 0]


class TestInvoke:
    def test_invoke_after_getitem_records_call(self):
        """invoke() always records, even when the last step is not getattr."""
        pipe = Selector["fn"].invoke(1, 2)
        assert pipe.steps[-1] == ("call", (1, 2), {})

    def test_invoke_calls_function_in_data(self):
        data = {"fn": lambda x, y: x + y}
        assert Selector["fn"].invoke(3, 4).apply(data) == 7

    def test_invoke_with_kwargs(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        data = {"fn": greet}
        assert Selector["fn"].invoke("Alice", greeting="Hi").apply(data) == "Hi, Alice!"

    def test_invoke_after_getattr_also_records(self):
        """invoke() always records regardless of context."""
        pipe = Selector.upper.invoke()
        assert pipe.steps[-1] == ("call", (), {})


class TestCompose:
    def test_add_composes_two_selectors(self):
        head = Selector["a"]
        tail = Selector["b"]
        assert (head + tail).apply({"a": {"b": 42}}) == 42

    def test_add_does_not_mutate_left_operand(self):
        a = Selector["a"]
        b = Selector["b"]
        steps_before = a.steps
        _ = a + b
        assert a.steps == steps_before

    def test_add_does_not_mutate_right_operand(self):
        b = Selector["b"]
        a = Selector["a"]
        steps_before = b.steps
        _ = a + b
        assert b.steps == steps_before

    def test_add_three_selectors(self):
        pipe = Selector["a"] + Selector["b"] + Selector["c"]
        assert pipe.apply({"a": {"b": {"c": 99}}}) == 99

    def test_add_non_selector_raises_type_error(self):
        with pytest.raises(TypeError):
            _ = Selector["x"] + 1

    def test_add_with_empty_selector(self):
        pipe = Selector["x"] + Selector
        assert pipe.apply({"x": 7}) == 7


class TestMisc:
    def test_empty_selector_is_identity(self):
        data = {"x": 42}
        assert Selector().apply(data) is data

    def test_repr_contains_class_name(self):
        assert repr(Selector["a"][:]).startswith("Selector(")

    def test_repr_contains_step_kinds(self):
        r = repr(Selector["a"][:])
        assert "getitem" in r
        assert "map" in r

    def test_pickle_roundtrip(self):
        pipe = Selector["annotations"][:]
        restored = pickle.loads(pickle.dumps(pipe))
        assert restored.steps == pipe.steps

    def test_pickle_empty_selector(self):
        restored = pickle.loads(pickle.dumps(Selector))
        assert restored.steps == ()

    def test_wrong_arity_on_evaluation_raises(self):
        with pytest.raises(TypeError):
            Selector["x"](1, 2)  # two args; last step is getitem → tries to evaluate

    def test_call_with_kwargs_on_non_getattr_raises(self):
        with pytest.raises(TypeError):
            Selector["x"](data={"x": 1})  # kwargs not allowed for evaluation


class TestIncludeKeys:
    def test_single_getitem(self):
        assert Selector["a"]["b"]({"a": {"b": 12}}, include_keys=True) == {"b": 12}

    def test_map_then_getitem(self):
        result = Selector[:]["a"]([{"a": 1}, {"a": 2}], include_keys=True)
        assert result == [{"a": 1}, {"a": 2}]

    def test_map_then_multi(self):
        data = [{"a": 1, "b": 2, "c": 3}, {"a": 4, "c": 6, "b": 5}]
        result = Selector[:]["a", "b"](data, include_keys=True)
        assert result == [{"a": 1, "b": 2}, {"a": 4, "b": 5}]

    def test_int_key_wrapped(self):
        assert Selector[0]([10, 20, 30], include_keys=True) == {0: 10}

    def test_flag_false_is_unchanged(self):
        assert Selector["x"]({"x": 7}, include_keys=False) == 7

    def test_apply_path(self):
        assert Selector["x"].apply({"x": 7}, include_keys=True) == {"x": 7}

    def test_slice_terminal_ignored(self):
        assert Selector[1:3]([0, 1, 2, 3], include_keys=True) == [1, 2]

    def test_call_terminal_ignored(self):
        assert Selector["x"].upper().apply({"x": "hi"}, include_keys=True) == "HI"

    def test_map_terminal_ignored(self):
        assert Selector["a"][:]({"a": [1, 2, 3]}, include_keys=True) == [1, 2, 3]

    def test_empty_selector_ignored(self):
        data = {"x": 1}
        assert Selector().apply(data, include_keys=True) is data


class TestIncludeNull:
    def test_missing_key_returns_none(self):
        assert Selector["a"]["missing"]({"a": {}}, include_null=True) is None

    def test_missing_top_level_key(self):
        assert Selector["nope"]({"a": 1}, include_null=True) is None

    def test_present_key_unaffected(self):
        assert Selector["a"]({"a": 42}, include_null=True) == 42

    def test_missing_key_propagates_through_chain(self):
        # Once a step fails, the _MISSING sentinel threads through; remaining steps are skipped
        assert Selector["x"]["y"]["z"]({"x": {}}, include_null=True) is None

    def test_missing_index_returns_none(self):
        assert Selector[5]([1, 2, 3], include_null=True) is None

    def test_multi_partial_missing(self):
        result = Selector["a", "b"]({"a": 1}, include_null=True)
        assert result == [1, None]

    def test_multi_all_missing(self):
        result = Selector["a", "b"]({}, include_null=True)
        assert result == [None, None]

    def test_map_with_partial_missing(self):
        data = [{"x": 1}, {"y": 2}, {"x": 3}]
        assert Selector[:]["x"](data, include_null=True) == [1, None, 3]

    def test_apply_path(self):
        assert Selector["missing"].apply({}, include_null=True) is None

    def test_flag_false_raises(self):
        with pytest.raises(KeyError):
            Selector["missing"]({"a": 1}, include_null=False)

    def test_combined_include_keys_and_null(self):
        result = Selector["a"]["missing"]({"a": {}}, include_null=True, include_keys=True)
        assert result == {"missing": None}

    def test_combined_map_keys_and_null(self):
        data = [{"x": 1}, {"y": 2}]
        result = Selector[:]["x"](data, include_null=True, include_keys=True)
        assert result == [{"x": 1}, {"x": None}]


class TestAliasKeys:
    # ── dict order is now {alias: access_key} ──────────────────────────────

    def test_single_alias_with_include_keys(self):
        assert Selector[{"a_alias": "a"}]({"a": 1}, include_keys=True) == {"a_alias": 1}

    def test_single_alias_without_include_keys_returns_raw(self):
        assert Selector[{"a_alias": "a"}]({"a": 1}) == 1

    def test_multi_all_aliased(self):
        result = Selector[{"x": "a"}, {"y": "b"}]({"a": 1, "b": 2}, include_keys=True)
        assert result == {"x": 1, "y": 2}

    def test_multi_partial_alias(self):
        result = Selector[{"x": "a"}, "b"]({"a": 1, "b": 2}, include_keys=True)
        assert result == {"x": 1, "b": 2}

    def test_multi_int_keys_aliased(self):
        result = Selector[{"first": 0}, 2]([10, 20, 30], include_keys=True)
        assert result == {"first": 10, 2: 30}

    def test_map_then_aliased_multi(self):
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = Selector[:][{"x": "a"}, "b"](data, include_keys=True)
        assert result == [{"x": 1, "b": 2}, {"x": 3, "b": 4}]

    def test_alias_with_include_null_partial_miss(self):
        result = Selector[{"x": "a"}, {"y": "b"}]({"a": 1}, include_keys=True, include_null=True)
        assert result == {"x": 1, "y": None}

    def test_empty_dict_raises(self):
        with pytest.raises(TypeError, match="single-entry"):
            Selector[{}]

    def test_multi_entry_dict_standalone_raises(self):
        with pytest.raises(TypeError, match="single-entry"):
            Selector[{"x": "a", "y": "b"}]

    def test_multi_entry_dict_inside_tuple_raises(self):
        with pytest.raises(TypeError, match="single-entry"):
            Selector[{"x": "a", "y": "b"}, "c"]

    def test_mixed_access_key_types_raise(self):
        with pytest.raises(TypeError, match="homogeneous"):
            Selector[{"x": "a"}, 0]

    def test_pickle_roundtrip_with_alias(self):
        import pickle
        pipe = Selector[{"a_alias": "a"}, "b"]
        restored = pickle.loads(pickle.dumps(pipe))
        assert restored.steps == pipe.steps

    # ── Selector-valued access ─────────────────────────────────────────────

    def test_selector_alias_single_with_include_keys(self):
        sub = Selector["a"]["b"]
        result = Selector[{"v": sub}]({"a": {"b": 9}}, include_keys=True)
        assert result == {"v": 9}

    def test_selector_alias_single_without_include_keys_returns_raw(self):
        sub = Selector["a"]["b"]
        assert Selector[{"v": sub}]({"a": {"b": 9}}) == 9

    def test_selector_alias_multi_with_include_keys(self):
        name_sel = Selector["name"]["first_name", "last_name"]
        data = {"employees": [
            {"name": {"first_name": "Alice", "last_name": "Smith"}, "adress": "1 Main St"},
            {"name": {"first_name": "Bob",   "last_name": "Jones"}, "adress": "2 Oak Ave"},
        ]}
        result = Selector["employees"][:][{"name": name_sel}, "adress"](data, include_keys=True)
        assert result == [
            {"name": ["Alice", "Smith"], "adress": "1 Main St"},
            {"name": ["Bob",   "Jones"], "adress": "2 Oak Ave"},
        ]

    def test_selector_alias_multi_without_include_keys_returns_list(self):
        sub = Selector["x"]
        result = Selector[{"v": sub}, "y"]({"x": 1, "y": 2})
        assert result == [1, 2]

    def test_bare_selector_as_plain_key_raises(self):
        with pytest.raises(TypeError, match="must be aliased"):
            Selector[Selector["a"]]

    def test_bare_selector_inside_multi_raises(self):
        with pytest.raises(TypeError, match="must be aliased"):
            Selector[Selector["a"], "b"]

    def test_pickle_roundtrip_with_selector_alias(self):
        import pickle
        sub = Selector["a"]["b"]
        pipe = Selector[{"v": sub}]
        restored = pickle.loads(pickle.dumps(pipe))
        # Verify the restored selector produces identical results (Selector has no __eq__,
        # so comparing .steps directly would fail due to identity checks on nested Selectors)
        data = {"a": {"b": 42}}
        assert restored(data, include_keys=True) == pipe(data, include_keys=True)
