#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "nanodjango",
#     "django-q-signals",
#     "django-q2",
# ]
# ///
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from nanodjango import Django

# Initialize nanodjango with settings
app = Django(
    INSTALLED_APPS=[
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django_q",
    ],
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(__file__).parent / "demo.db",
        }
    },
    Q_CLUSTER={
        "name": "demo",
        "workers": 2,
        "recycle": 500,
        "timeout": 60,
        "compress": True,
        "save_limit": 250,
        "queue_limit": 500,
        "cpu_affinity": 1,
        "label": "Django Q2 Demo",
        "orm": "default",
    },
    SECRET_KEY="demo-secret-key",
    DEBUG=True,
    ALLOWED_HOSTS=["*"],
)

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpResponse
from django_q.models import Task

from django_q_signals import async_receiver


# Models
@app.admin
class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "demo"


@app.admin
class EmailLog(models.Model):
    recipient = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    sent_at = models.DateTimeField(auto_now_add=True)
    processing_time = models.FloatField()
    handler_type = models.CharField(max_length=20)

    class Meta:
        app_label = "demo"


@app.admin
class ProcessingLog(models.Model):
    article_id = models.IntegerField()
    task = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)

    class Meta:
        app_label = "demo"


# Simulated heavy operations
def send_notification_email(article, handler_type="unknown"):
    """Simulate sending email - takes 2 seconds"""
    time.sleep(2)
    EmailLog.objects.create(
        recipient=f"{article.author}@example.com",
        subject=f"New article: {article.title}",
        processing_time=2.0,
        handler_type=handler_type,
    )


def update_search_index(article):
    """Simulate search index update - takes 1 second"""
    time.sleep(1)
    ProcessingLog.objects.create(
        article_id=article.id,
        task="search_index",
        completed_at=datetime.now(),
        status="completed",
    )


def generate_thumbnails(article):
    """Simulate thumbnail generation - takes 1.5 seconds"""
    time.sleep(1.5)
    ProcessingLog.objects.create(
        article_id=article.id,
        task="thumbnails",
        completed_at=datetime.now(),
        status="completed",
    )


# Signal handler flags
sync_handlers_enabled = False
async_handlers_enabled = False


# SYNCHRONOUS HANDLERS (for comparison)
@receiver(post_save, sender=Article)
def sync_article_handler(sender, instance, created=False, **kwargs):
    if not sync_handlers_enabled or not created:
        return

    # These will block the request!
    send_notification_email(instance, "sync")
    update_search_index(instance)
    generate_thumbnails(instance)


# ASYNCHRONOUS HANDLERS (using django-q-signals)
@async_receiver(post_save, sender=Article)
def async_article_handler(sender, instance, **kwargs):
    created = kwargs.get("created", False)
    if not async_handlers_enabled or not created:
        return

    # These run in the background via Django Q2!
    send_notification_email(instance, "async")
    update_search_index(instance)
    generate_thumbnails(instance)


# Views
@app.route("/")
def index(request):
    """Main UI with demo controls"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Django Q Signals Demo</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                background: #f4f4f4;
                margin: 0;
                padding: 0;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }
            h1 {
                color: #2c3e50;
                text-align: center;
                margin-bottom: 10px;
            }
            .subtitle {
                text-align: center;
                color: #7f8c8d;
                margin-bottom: 30px;
            }
            .demo-section {
                background: white;
                border-radius: 8px;
                padding: 25px;
                margin: 20px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .demo-section h2 {
                color: #34495e;
                margin-top: 0;
            }
            .demo-section p {
                color: #7f8c8d;
                margin: 10px 0 20px 0;
            }
            button {
                background: #3498db;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 4px;
                font-size: 16px;
                cursor: pointer;
                transition: background 0.3s;
            }
            button:hover {
                background: #2980b9;
            }
            button:disabled {
                background: #95a5a6;
                cursor: not-allowed;
            }
            .sync-button {
                background: #e74c3c;
            }
            .sync-button:hover {
                background: #c0392b;
            }
            .timing {
                font-size: 28px;
                font-weight: bold;
                margin: 15px 0;
            }
            .timing.fast {
                color: #27ae60;
            }
            .timing.slow {
                color: #e74c3c;
            }
            .result {
                margin-top: 20px;
                padding: 15px;
                background: #ecf0f1;
                border-radius: 4px;
                min-height: 60px;
            }
            .log-entry {
                padding: 10px;
                border-bottom: 1px solid #ecf0f1;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .log-entry:last-child {
                border-bottom: none;
            }
            .badge {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }
            .badge.sync {
                background: #e74c3c;
                color: white;
            }
            .badge.async {
                background: #27ae60;
                color: white;
            }
            .queue-status {
                display: flex;
                gap: 20px;
                margin-top: 15px;
            }
            .status-item {
                flex: 1;
                text-align: center;
                padding: 10px;
                background: #ecf0f1;
                border-radius: 4px;
            }
            .status-item .number {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
            }
            .status-item .label {
                font-size: 12px;
                color: #7f8c8d;
                text-transform: uppercase;
            }
            .spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #3498db;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-left: 10px;
                vertical-align: middle;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .info-box {
                background: #3498db;
                color: white;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
            }
            .info-box h3 {
                margin-top: 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Django Q Signals Demo</h1>
            <div class="subtitle">See the difference between synchronous and asynchronous signal handlers</div>

            <div class="info-box">
                <h3>How this demo works:</h3>
                <p>When an Article is created, three time-consuming tasks are triggered:</p>
                <ul>
                    <li>📧 Send notification email (2 seconds)</li>
                    <li>🔍 Update search index (1 second)</li>
                    <li>🖼️ Generate thumbnails (1.5 seconds)</li>
                </ul>
                <p><strong>Total processing time: 4.5 seconds</strong></p>
            </div>

            <div class="demo-section">
                <h2>❌ Synchronous Handlers (Traditional Django)</h2>
                <p>Signal handlers run during the request, blocking the response until all processing is complete.</p>
                <button class="sync-button" onclick="createArticle('sync')" id="sync-btn">
                    Create Article (Sync)
                </button>
                <div id="sync-result" class="result"></div>
            </div>

            <div class="demo-section">
                <h2>✅ Asynchronous Handlers (With django-q-signals)</h2>
                <p>Signal handlers are queued and processed in the background, returning immediately.</p>
                <button onclick="createArticle('async')" id="async-btn">
                    Create Article (Async)
                </button>
                <div id="async-result" class="result"></div>
            </div>

            <div class="demo-section">
                <h2>📊 Queue Status</h2>
                <div id="queue-status" class="queue-status">
                    <div class="status-item">
                        <div class="number" id="pending-count">0</div>
                        <div class="label">Pending</div>
                    </div>
                    <div class="status-item">
                        <div class="number" id="completed-count">0</div>
                        <div class="label">Completed</div>
                    </div>
                    <div class="status-item">
                        <div class="number" id="failed-count">0</div>
                        <div class="label">Failed</div>
                    </div>
                </div>
            </div>

            <div class="demo-section">
                <h2>📝 Recent Processing Logs</h2>
                <div id="logs">
                    <p style="text-align: center; color: #95a5a6;">No logs yet. Create an article to see processing logs.</p>
                </div>
            </div>
        </div>

        <script>
            function createArticle(mode) {
                const button = document.getElementById(`${mode}-btn`);
                const resultDiv = document.getElementById(`${mode}-result`);

                button.disabled = true;
                resultDiv.innerHTML = '<span class="spinner"></span> Processing...';

                const start = Date.now();

                fetch(`/api/article/${mode}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                })
                .then(r => r.json())
                .then(data => {
                    const elapsed = Date.now() - start;
                    const speedClass = elapsed < 500 ? 'fast' : 'slow';

                    resultDiv.innerHTML = `
                        <div class="timing ${speedClass}">⏱️ ${elapsed}ms</div>
                        <div>Article ID: ${data.article_id}</div>
                        <div>Mode: ${data.mode}</div>
                    `;

                    button.disabled = false;
                    updateLogs();
                    updateQueueStatus();
                })
                .catch(err => {
                    resultDiv.innerHTML = `<div style="color: red;">Error: ${err.message}</div>`;
                    button.disabled = false;
                });
            }

            function updateLogs() {
                fetch('/api/logs')
                    .then(r => r.json())
                    .then(data => {
                        const logsDiv = document.getElementById('logs');
                        if (data.emails.length === 0) {
                            return;
                        }

                        let html = '<h4>Email Notifications:</h4>';
                        data.emails.forEach(email => {
                            const date = new Date(email.sent_at);
                            html += `
                                <div class="log-entry">
                                    <div>
                                        <span class="badge ${email.handler_type}">${email.handler_type}</span>
                                        ${email.subject}
                                    </div>
                                    <div>${date.toLocaleTimeString()}</div>
                                </div>
                            `;
                        });

                        if (data.tasks.length > 0) {
                            html += '<h4>Background Tasks:</h4>';
                            data.tasks.forEach(task => {
                                const date = new Date(task.started_at);
                                html += `
                                    <div class="log-entry">
                                        <div>
                                            Article #${task.article_id} - ${task.task}
                                        </div>
                                        <div>${task.status}</div>
                                    </div>
                                `;
                            });
                        }

                        logsDiv.innerHTML = html;
                    });
            }

            function updateQueueStatus() {
                fetch('/api/queue-status')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('pending-count').textContent = data.pending;
                        document.getElementById('completed-count').textContent = data.completed;
                        document.getElementById('failed-count').textContent = data.failed;
                    });
            }

            // Poll for updates
            setInterval(() => {
                updateLogs();
                updateQueueStatus();
            }, 2000);

            // Initial load
            updateQueueStatus();
        </script>
    </body>
    </html>
    """
    return HttpResponse(html)


@app.api.post("/article/sync")
def create_article_sync(request):
    """Create article with synchronous signal handlers"""
    global sync_handlers_enabled, async_handlers_enabled

    # Enable only sync handlers
    sync_handlers_enabled = True
    async_handlers_enabled = False

    start_time = time.time()

    article = Article.objects.create(
        title=f"Article created at {datetime.now().strftime('%H:%M:%S')}",
        content="This article was processed with synchronous handlers that block the request.",
        author="Demo User",
    )

    elapsed = time.time() - start_time

    # Reset flags
    sync_handlers_enabled = False

    return {"article_id": article.id, "processing_time": elapsed, "mode": "synchronous"}


@app.api.post("/article/async")
def create_article_async(request):
    """Create article with asynchronous signal handlers"""
    global sync_handlers_enabled, async_handlers_enabled

    # Enable only async handlers
    sync_handlers_enabled = False
    async_handlers_enabled = True

    start_time = time.time()

    article = Article.objects.create(
        title=f"Article created at {datetime.now().strftime('%H:%M:%S')}",
        content="This article was processed with async handlers that run in the background.",
        author="Demo User",
    )

    elapsed = time.time() - start_time

    # Reset flags
    async_handlers_enabled = False

    return {
        "article_id": article.id,
        "processing_time": elapsed,
        "mode": "asynchronous",
    }


@app.api.get("/logs")
def get_logs(request):
    """Get processing logs"""
    emails = EmailLog.objects.all().order_by("-sent_at")[:5]
    tasks = ProcessingLog.objects.all().order_by("-started_at")[:10]

    return {
        "emails": [
            {
                "recipient": e.recipient,
                "subject": e.subject,
                "sent_at": e.sent_at.isoformat(),
                "processing_time": e.processing_time,
                "handler_type": e.handler_type,
            }
            for e in emails
        ],
        "tasks": [
            {
                "article_id": t.article_id,
                "task": t.task,
                "status": t.status,
                "started_at": t.started_at.isoformat(),
            }
            for t in tasks
        ],
    }


@app.api.get("/queue-status")
def queue_status(request):
    """Get Django Q2 queue status"""
    pending = Task.objects.filter(success__isnull=True).count()
    completed = Task.objects.filter(success=True).count()
    failed = Task.objects.filter(success=False).count()

    return {"pending": pending, "completed": completed, "failed": failed}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "qcluster":
        app.manage(("qcluster",))
    else:
        # Run the web server
        app.run()
