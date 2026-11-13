from dataclasses import dataclass, field

import pytest

from itemadapter import ItemAdapter
from itemadapter.adapter import _DELETED_FIELDS_ATTR
from tests import DataClassItem, DataClassItemPlainDefaults


@dataclass
class DataClassItemMixedDefaults:
    plain: str = "plain-default"
    factory: list = field(default_factory=lambda: ["factory-default"])
    required: str = ""


@dataclass(slots=True)
class SlottedDataClassItem:
    plain: str = "plain-default"
    factory: list = field(default_factory=list)


@dataclass(slots=True, weakref_slot=True)
class WeakrefableSlottedDataClassItem:
    plain: str = "plain-default"
    value: int = 0


@dataclass(frozen=True)
class FrozenDataClassItem:
    plain: str = "plain-default"
    value: int = 1


def _assert_field_absent(adapter: ItemAdapter, field_name: str) -> None:
    # Four viewpoints must agree: view, membership, field count, serialization.
    assert field_name not in adapter
    assert field_name not in list(adapter.keys())
    assert field_name not in dict(adapter)
    assert adapter.asdict().get(field_name) is None
    with pytest.raises(KeyError):
        adapter[field_name]
    assert adapter.get(field_name, "fallback") == "fallback"
    assert adapter.pop(field_name, "fallback") == "fallback"


class TestPlainDefaultDeletion:
    def test_delete_plain_default_field(self):
        item = DataClassItemPlainDefaults(name="asdf", value=1234)
        adapter = ItemAdapter(item)
        del adapter["name"]
        _assert_field_absent(adapter, "name")
        assert len(adapter) == 1
        assert list(adapter) == ["value"]
        # The class-level default must not leak back through the adapter.
        assert adapter.asdict() == {"value": 1234}

    def test_delete_all_plain_default_fields(self):
        item = DataClassItemPlainDefaults(name="asdf", value=1234)
        adapter = ItemAdapter(item)
        del adapter["name"]
        del adapter["value"]
        assert len(adapter) == 0
        assert list(adapter) == []
        assert dict(adapter) == {}
        assert adapter.asdict() == {}

    def test_fresh_adapter_reflects_deletion(self):
        item = DataClassItemPlainDefaults(name="asdf", value=1234)
        adapter = ItemAdapter(item)
        del adapter["name"]
        # A brand new adapter over the same item must see the same state.
        fresh = ItemAdapter(item)
        _assert_field_absent(fresh, "name")
        assert fresh.asdict() == {"value": 1234}
        assert len(fresh) == 1

    def test_double_delete_raises_keyerror(self):
        adapter = ItemAdapter(DataClassItemPlainDefaults(name="asdf", value=1234))
        del adapter["name"]
        with pytest.raises(KeyError) as exc_info:
            del adapter["name"]
        assert exc_info.value.args == ("name",)

    def test_undefined_field_delete_raises_keyerror(self):
        adapter = ItemAdapter(DataClassItemPlainDefaults())
        with pytest.raises(KeyError, match="does not support field"):
            del adapter["undefined_field"]

    def test_restore_after_delete(self):
        item = DataClassItemPlainDefaults(name="asdf", value=1234)
        adapter = ItemAdapter(item)
        del adapter["name"]
        assert "name" not in adapter
        adapter["name"] = "restored"
        assert "name" in adapter
        assert adapter["name"] == "restored"
        assert adapter.asdict() == {"name": "restored", "value": 1234}
        # The restored value survives a new adapter on the same item.
        fresh = ItemAdapter(item)
        assert fresh["name"] == "restored"

    def test_restore_is_visible_in_fresh_adapter(self):
        item = DataClassItemPlainDefaults(name="asdf", value=1234)
        adapter = ItemAdapter(item)
        del adapter["name"]
        adapter["name"] = "restored"
        del adapter["name"]
        fresh = ItemAdapter(item)
        _assert_field_absent(fresh, "name")


@pytest.mark.parametrize(
    ("item_class", "deleted_field"),
    [
        (DataClassItem, "name"),  # default_factory declaration
        (DataClassItemPlainDefaults, "name"),  # plain default declaration
        (DataClassItemMixedDefaults, "plain"),
        (DataClassItemMixedDefaults, "factory"),
    ],
)
def test_delete_semantics_independent_of_declaration(item_class, deleted_field):
    kwargs = {
        "name": "asdf",
        "value": 1234,
        "plain": "x",
        "factory": [1],
        "required": "r",
    }
    item = item_class(**{key: value for key, value in kwargs.items() if hasattr(item_class, key)})
    adapter = ItemAdapter(item)
    original_len = len(adapter)
    del adapter[deleted_field]
    _assert_field_absent(adapter, deleted_field)
    assert len(adapter) == original_len - 1
    fresh = ItemAdapter(item)
    _assert_field_absent(fresh, deleted_field)
    assert len(fresh) == original_len - 1


def test_mixed_defaults_each_kind():
    item = DataClassItemMixedDefaults(plain="p", factory=["f"], required="r")
    adapter = ItemAdapter(item)
    assert set(adapter) == {"plain", "factory", "required"}

    del adapter["plain"]
    _assert_field_absent(adapter, "plain")
    assert set(adapter) == {"factory", "required"}

    del adapter["factory"]
    _assert_field_absent(adapter, "factory")
    assert set(adapter) == {"required"}

    fresh = ItemAdapter(item)
    assert set(fresh) == {"required"}
    assert fresh.asdict() == {"required": "r"}


def test_slotted_dataclass_deletion():
    item = SlottedDataClassItem(plain="p", factory=["f"])
    adapter = ItemAdapter(item)
    del adapter["plain"]
    _assert_field_absent(adapter, "plain")
    del adapter["factory"]
    assert len(adapter) == 0
    fresh = ItemAdapter(item)
    assert len(fresh) == 0
    with pytest.raises(KeyError):
        del adapter["plain"]

    adapter2 = ItemAdapter(SlottedDataClassItem(plain="p"))
    del adapter2["plain"]
    with pytest.raises(KeyError):
        del adapter2["plain"]


def test_weakrefable_slotted_dataclass_deletion():
    item = WeakrefableSlottedDataClassItem(plain="p", value=2)
    adapter = ItemAdapter(item)
    del adapter["plain"]
    _assert_field_absent(adapter, "plain")
    # The tracking state must carry over to a fresh adapter even though the
    # item has no __dict__ (it is tracked through its __weakref__ slot).
    fresh = ItemAdapter(item)
    _assert_field_absent(fresh, "plain")
    assert fresh.asdict() == {"value": 2}
    with pytest.raises(KeyError):
        del adapter["plain"]
    adapter["plain"] = "restored"
    assert ItemAdapter(item)["plain"] == "restored"


def test_frozen_dataclass_deletion():
    item = FrozenDataClassItem(plain="p", value=2)
    adapter = ItemAdapter(item)
    del adapter["plain"]
    _assert_field_absent(adapter, "plain")
    assert adapter.asdict() == {"value": 2}
    fresh = ItemAdapter(item)
    _assert_field_absent(fresh, "plain")
    with pytest.raises(KeyError):
        del adapter["plain"]


def test_deleted_field_stays_hidden_after_manually_readding_instance_attr():
    item = DataClassItemPlainDefaults(name="asdf", value=1234)
    adapter = ItemAdapter(item)
    del adapter["name"]
    # Even though the class attribute still provides the default, the adapter
    # view must keep hiding the field until it is set through the adapter.
    assert hasattr(item, "name")
    _assert_field_absent(ItemAdapter(item), "name")


def test_tracking_attribute_is_hidden_from_adapter_view():
    item = DataClassItemPlainDefaults(name="asdf", value=1234)
    adapter = ItemAdapter(item)
    del adapter["name"]
    # The internal bookkeeping attribute must never leak into any adapter view.
    assert _DELETED_FIELDS_ATTR not in adapter
    assert _DELETED_FIELDS_ATTR not in adapter.field_names()
    assert _DELETED_FIELDS_ATTR not in dict(adapter)
    assert _DELETED_FIELDS_ATTR not in adapter.asdict()


def test_user_attribute_sharing_tracking_name_is_preserved():
    @dataclass
    class CollidingItem:
        _itemadapter_deleted_fields: str = "user-value"
        name: str = "default name"

    item = CollidingItem()
    adapter = ItemAdapter(item)
    del adapter["name"]
    # The user-defined attribute is untouched and still visible as a field.
    assert item._itemadapter_deleted_fields == "user-value"
    assert adapter["_itemadapter_deleted_fields"] == "user-value"
    _assert_field_absent(adapter, "name")
    # A fresh adapter on the same item must honor the tracked deletion.
    _assert_field_absent(ItemAdapter(item), "name")
    # Restoring through the adapter works without touching the user attribute.
    adapter["name"] = "restored"
    assert adapter["name"] == "restored"
    assert item._itemadapter_deleted_fields == "user-value"
