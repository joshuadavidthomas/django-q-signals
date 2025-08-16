from __future__ import annotations

import sys
from collections.abc import Callable
from collections.abc import Coroutine
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any

from asgiref.sync import async_to_sync
from django.apps import apps
from django.db import models
from django.dispatch import Signal
from django.dispatch import receiver
from django_q.tasks import async_task

Sender = type[models.Model] | None
Instance = models.Model | None
SignalHandler = Callable[[Sender, Instance], Coroutine[Any, Any, None] | None]


def async_receiver(
    signal: Signal | list[Signal] | tuple[Signal, ...],
    sender: Sender = None,
    **options: Any,
) -> Callable[[SignalHandler], SignalHandler]:
    """
    Decorator to register an async signal receiver using Django Q2.

    This decorator has the same signature as Django's @receiver decorator
    but offloads the signal handler to Django Q2's task queue for async processing.

    Args:
        signal: The Django signal to connect to
        sender: Optional sender to filter signals by
        **options: Additional options passed to the signal connection
            (e.g., dispatch_uid, weak)

    Returns:
        A decorator function that registers the async signal handler
    """

    def decorator(func: SignalHandler) -> SignalHandler:
        # Create and attach a Django Q2-compatible wrapper function to the module
        task_path = _create_async_task_wrapper(func)

        @wraps(func)
        def signal_handler(**kwargs: Any) -> None:
            sender: Sender = kwargs.get("sender")
            instance: Instance = kwargs.get("instance")

            # Skip Django Q2's internal models to prevent infinite recursion
            if sender and sender._meta.app_label == "django_q":
                return

            sender_label = _get_model_label(sender)
            instance_label = _get_model_label(instance)

            serializable_kwargs = _serialize_signal_kwargs(kwargs)

            async_task(
                task_path,
                sender_label,
                instance_label,
                instance.pk if instance else None,
                serializable_kwargs,
            )

        # Handle list of signals like Django's receiver does
        if isinstance(signal, (list, tuple)):
            for s in signal:
                receiver(s, sender=sender, **options)(signal_handler)
        else:
            receiver(signal, sender=sender, **options)(signal_handler)

        return func

    return decorator


def _create_async_task_wrapper(func: SignalHandler) -> str:
    task_name = f"{func.__name__}_task"
    task_path = f"{func.__module__}.{task_name}"

    handler = async_to_sync(func) if iscoroutinefunction(func) else func

    def async_task_func(
        sender_label: str | None,
        instance_label: str | None,
        instance_id: Any,
        signal_kwargs: dict[str, Any],
    ) -> Any:
        # reconstruct sender
        sender: Sender = None
        if sender_label:
            app_label, model_name = sender_label.rsplit(".", 1)
            sender = apps.get_model(app_label, model_name)

        # reconstruct instance
        instance: Instance = None
        if instance_label:
            app_label, model_name = instance_label.rsplit(".", 1)
            model_class = apps.get_model(app_label, model_name)
            try:
                instance = model_class.objects.get(pk=instance_id)
            except model_class.DoesNotExist:
                # Instance was deleted - pass None to the handler and add the pk
                # to the kwargs so handlers can at least do *something* with it
                instance = None
                signal_kwargs["_instance_pk"] = instance_id

        # reconstruct update_fields back into a frozenset
        if (
            "update_fields" in signal_kwargs
            and signal_kwargs["update_fields"] is not None
        ):
            signal_kwargs["update_fields"] = frozenset(signal_kwargs["update_fields"])

        return handler(sender, instance, **signal_kwargs)

    async_task_func.__name__ = task_name
    async_task_func.__module__ = func.__module__

    module = sys.modules[func.__module__]
    setattr(module, task_name, async_task_func)

    return task_path


def _get_model_label(model: Sender | Instance) -> str | None:
    return f"{model._meta.app_label}.{model._meta.model_name}" if model else None


def _serialize_signal_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Convert signal kwargs into a serializable format for Django Q2."""
    serializable_kwargs: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key in ("signal", "sender", "instance"):
            # Skip these as they're handled separately
            continue
        elif key == "update_fields" and value is not None:
            # interally in Django's Model.save method, update_fields are changed to a frozenset
            # and passed to the model signals like that -- so we need to convert to a list for
            # serialization
            # Ref: https://github.com/django/django/blob/cd0966cd4e37da8e6153cbf57c194dce29caaddc/django/db/models/base.py#L846
            serializable_kwargs[key] = list(value)
        elif isinstance(
            value, str | int | float | bool | list | dict | tuple | type(None)
        ):
            serializable_kwargs[key] = value
    return serializable_kwargs
