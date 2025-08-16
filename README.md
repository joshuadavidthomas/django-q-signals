# django-q-signals

<!-- [[[cog
import subprocess
import cog

from noxfile import DJ_VERSIONS
from noxfile import PY_VERSIONS

cog.outl("[![PyPI](https://img.shields.io/pypi/v/django-q-signals)](https://pypi.org/project/django-q-signals/)")
cog.outl("![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-q-signals)")
cog.outl(f"![Django Version](https://img.shields.io/badge/django-{'%20%7C%20'.join(DJ_VERSIONS)}-%2344B78B?labelColor=%23092E20)")
]]] -->
[![PyPI](https://img.shields.io/pypi/v/django-q-signals)](https://pypi.org/project/django-q-signals/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-q-signals)
![Django Version](https://img.shields.io/badge/django-4.2%20%7C%205.1%20%7C%205.2%20%7C%20main-%2344B78B?labelColor=%23092E20)
<!-- [[[end]]] -->

Process Django signals asynchronously with [Django Q2](https://github.com/django-q2/django-q2).

## Requirements

<!-- [[[cog
import subprocess
import cog

from noxfile import DJ_VERSIONS
from noxfile import PY_VERSIONS

cog.outl(f"- Python {', '.join([version for version in PY_VERSIONS])}")
cog.outl(f"- Django {', '.join([version for version in DJ_VERSIONS if version != 'main'])}")
]]] -->
- Python 3.10, 3.11, 3.12, 3.13
- Django 4.2, 5.1, 5.2
<!-- [[[end]]] -->

## Installation

1. Install the package from [PyPI](https://pypi.org/project/django-q-signals).

    ```bash
    python -m pip install django-q-signals

    # or if you like the new hotness

    uv add django-q-signals
    uv sync
    ```

2. Ensure Django Q2 is installed and correctly configured for your project.

## Getting Started

Django signals run synchronously by default, potentially blocking your request/response cycle while they process. Even async handlers, which Django's signals support, still block the request:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

from myapp.models import Article


@receiver(post_save, sender=Article)
async def notify_subscribers(sender, instance, **kwargs):
    # This async handler STILL blocks the request!
    for subscriber in instance.subscribers.all():
        await send_email_async(subscriber.email, f"New article: {instance.title}")

    # More blocking async operations
    await update_search_index_async(instance)
    await generate_thumbnails_async(instance)
    await ping_external_apis_async(instance)
```

You could manually offload this to Django Q2's task queue:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from myapp.models import Article


def process_article_task(article_id):
    article = Article.objects.get(pk=article_id)
    for subscriber in article.subscribers.all():
        send_email(subscriber.email, f"New article: {article.title}")
    update_search_index(article)
    generate_thumbnails(article)
    ping_external_apis(article)


@receiver(post_save, sender=Article)
def notify_subscribers(sender, instance, **kwargs):
    # Queue the task instead of running it now
    async_task('myapp.tasks.process_article_task', instance.pk)
```

But who wants to write all that boilerplate every time you need to offload a signal handler? (Yes, it's barely any boilerplate and the explicit version is arguably clearer, but let me have this.) 

Instead, `@async_receiver` can handle all this for you:

```python
from django.db.models.signals import post_save
from django_q_signals import async_receiver

from myapp.models import Article


@async_receiver(post_save, sender=Article)
def notify_subscribers(sender, instance, **kwargs):
    # This automatically runs in the background via Django Q2
    for subscriber in instance.subscribers.all():
        send_email(subscriber.email, f"New article: {instance.title}")
    update_search_index(instance)
    generate_thumbnails(instance)
    ping_external_apis(instance)
```

Your views return immediately while the heavy lifting happens in the background.

## Usage

The `@async_receiver` decorator transforms your signal handler into an asynchronous task by:

1. Creating a serializable wrapper function that Django Q2 can pickle
2. Registering that wrapper as a module-level function for Django Q2 to import
3. Intercepting signals and queuing tasks with serialized instance data
4. Reconstructing model instances from their primary keys when the task runs

This means your handler receives the same arguments as a normal signal handler, but runs in Django Q2's task queue instead of blocking the request.

The `@async_receiver` decorator accepts the same arguments as Django's `@receiver`:

- `signal`: One or more signals to connect to
- `sender`: Optional model class to filter signals
- `**kwargs`: Additional options like `dispatch_uid` for preventing duplicates

```python
# Prevent duplicate registrations with dispatch_uid
@async_receiver(post_save, sender=Article, dispatch_uid="unique_article_handler")
def process_article(sender, instance, **kwargs):
    generate_thumbnails(instance)

# Handle multiple signals with one handler
@async_receiver([post_save, post_delete], sender=Article)
def update_search_index(sender, instance, **kwargs):
    if kwargs.get('created', False):
        add_to_index(instance)
    elif instance is None:
        # Instance was deleted but pk is preserved
        if pk := kwargs.get('_instance_pk'):
            remove_from_index_by_id(pk)
```

Just like Django's `@receiver` decorator, `@async_receiver` supports async handlers:

```python
@async_receiver(post_save, sender=Article)
async def process_article_async(sender, instance, **kwargs):
    await external_api.notify(instance.id)
    await cache.invalidate(f"article_{instance.id}")
    return await generate_summary(instance.content)
```

Async handlers are automatically wrapped with `asgiref.sync.async_to_sync` for execution in Django Q2's worker processes, matching Django's `@receiver` behavior.

### Django Q2 Models

Django Q2's internal models are automatically excluded from async processing and cannot be used with the `@async_receiver`, to prevent infinite recursion. If you need to respond to Django Q2 model changes, use Django Q2's own [signals](https://django-q2.readthedocs.io/en/master/signals.html) or handle them manually using Django's standard `@receiver` decorator.

### Serialization

Model instances are serialized by their primary key and reconstructed when the task runs.

The `update_fields` parameter is converted to a `list` internally before passing to Django Q2's `async_task`, then converted back to a `frozenset` before passing through to your handler, maintaining Django's behavior.

Only serializable signal kwargs (strings, numbers, lists, dicts, etc.) are passed to the async handler

### Race Conditions

Since signal handlers decorated with `@async_receiver` run in a task queue asynchronously, there's a potential race condition where an instance might be deleted between when the signal fires and when the async task executes:

When an instance cannot be found during task execution, `None` is passed to your handler. However, the instance's primary key is preserved in `kwargs['_instance_pk']` so you can still identify which object was affected:

```python
@async_receiver(post_save, sender=Article)
def process_article(sender, instance, **kwargs):
    if instance is None:
        # Instance was deleted, but we have the pk
        article_id = kwargs.get('_instance_pk')
        logger.warning(f"Article {article_id} was deleted before processing")
        # Could still do cleanup based on the ID
        cleanup_article_artifacts(article_id)
        return

    # Normal processing
    generate_thumbnail(instance)
```

In particular, `post_save` signals with `created=False` (updates to existing instances) and `m2m_changed` signals are more prone to this race condition, since these often involve instances that might be deleted soon after modification. Newly created instances (`created=True`) are less likely to be immediately deleted, and for delete signals the instance is expected to be gone anyway.

Honestly, if you need a task to run regardless of instance deletion, you're better off using Django's built-in `@receiver` and calling `async_task` directly with the data you need, rather than using `@async_receiver`.

## Development

For detailed instructions on setting up a development environment and contributing to this project, see [CONTRIBUTING.md](CONTRIBUTING.md).

For release procedures, see [RELEASING.md](RELEASING.md).

## License

django-q-signals is licensed under the MIT license. See the [`LICENSE`](LICENSE) file for more information.
