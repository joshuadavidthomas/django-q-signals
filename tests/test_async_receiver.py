from __future__ import annotations

import sys
from functools import partial

import pytest
from django.db.models.signals import post_delete
from django.db.models.signals import post_save

from django_q_signals import async_receiver as _async_receiver

from .models import QSignalsModel

async_receiver = partial(_async_receiver, weak=False)


@pytest.fixture(autouse=True)
def cleanup_signals():
    post_save.receivers = []
    post_delete.receivers = []

    yield

    post_save.receivers = []
    post_delete.receivers = []


def test_decorator_returns_original_function():
    @async_receiver(post_save, sender=QSignalsModel)
    def handler(sender, instance, **kwargs): ...

    assert callable(handler)
    assert handler.__name__ == "handler"


def test_task_function_created_in_module():
    @async_receiver(post_save, sender=QSignalsModel)
    def handler(sender, instance, **kwargs): ...

    module = sys.modules[handler.__module__]

    assert hasattr(module, "handler_task")
    assert callable(module.handler_task)


@pytest.mark.django_db
def test_signal_triggers_handler_sync():
    result = {"called": False, "sender": None, "instance": None, "kwargs": None}

    @async_receiver(post_save, sender=QSignalsModel)
    def handler(sender, instance, **kwargs):
        result["called"] = True
        result["sender"] = sender
        result["instance"] = instance
        result["kwargs"] = kwargs

    instance = QSignalsModel.objects.create(name="Test", value=42)

    assert result["called"] is True
    assert result["sender"] == QSignalsModel
    assert result["instance"].pk == instance.pk
    assert result["instance"].name == "Test"
    assert result["kwargs"]["created"] is True


@pytest.mark.django_db
def test_multiple_signals_same_handler():
    result = {"save_count": 0, "delete_count": 0}

    @async_receiver([post_save, post_delete], sender=QSignalsModel)  # type: ignore[arg-type]
    def handler(sender, instance, **kwargs):
        if kwargs.get("created") is not None:
            result["save_count"] += 1
        else:
            result["delete_count"] += 1

    instance = QSignalsModel.objects.create(name="Test", value=10)

    assert result["save_count"] == 1

    instance.delete()

    assert result["delete_count"] == 1


@pytest.mark.django_db
def test_update_fields_serialization():
    result = {"update_fields": None}

    @async_receiver(post_save, sender=QSignalsModel)
    def handler(sender, instance, **kwargs):
        result["update_fields"] = kwargs.get("update_fields")

    instance = QSignalsModel.objects.create(name="Initial", value=1)

    instance.name = "Updated"
    # pass update_fields as list, Django converts to frozenset
    instance.save(update_fields=["name"])

    # comes back out as frozenset after passing through serialization needed
    # for passing to an async_task -- matching Django's signal receiver
    assert isinstance(result["update_fields"], frozenset)
    assert result["update_fields"] == frozenset({"name"})


@pytest.mark.django_db
def test_instance_deleted_before_async_execution():
    result = {"instance": "not_set", "pk": None}

    @async_receiver(post_save, sender=QSignalsModel)
    def handler(sender, instance, **kwargs):
        result["instance"] = instance
        result["pk"] = kwargs.get("_instance_pk")

    # Create and save a real instance
    instance = QSignalsModel.objects.create(name="Temporary", value=42)
    instance_id = instance.pk

    # Delete it to simulate it being deleted before async task runs
    instance.delete()

    # Now manually call the async task function with the deleted instance's ID
    module = sys.modules[handler.__module__]
    task_func = module.handler_task

    # This simulates the async task running after the instance was deleted
    task_func(
        "tests.qsignalsmodel",  # sender_label
        "tests.qsignalsmodel",  # instance_label
        instance_id,  # The ID of the now-deleted instance
        {},  # signal_kwargs
    )

    # The handler should receive None for instance but get the pk in kwargs
    assert result["instance"] is None
    assert result["pk"] == instance_id


@pytest.mark.django_db
def test_none_instance_handling():
    result = {"called": False, "instance": None}

    @async_receiver(post_save)
    def handler(sender, instance, **kwargs):
        result["called"] = True
        result["instance"] = instance

    post_save.send(sender=QSignalsModel, instance=None)

    assert result["called"] is True
    assert result["instance"] is None
