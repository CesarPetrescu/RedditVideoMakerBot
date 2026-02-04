/**
 * Reddit Video Maker Bot - Progress GUI JavaScript
 * Real-time progress tracking via WebSocket
 */

class ProgressTracker {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.currentJob = null;
        this.jobHistory = [];

        // DOM elements
        this.elements = {
            noJob: document.getElementById('no-job'),
            jobInfo: document.getElementById('job-info'),
            jobSubreddit: document.getElementById('job-subreddit'),
            jobTitle: document.getElementById('job-title'),
            jobStatusBadge: document.getElementById('job-status-badge'),
            overallProgressFill: document.getElementById('overall-progress-fill'),
            overallProgressText: document.getElementById('overall-progress-text'),
            stepsContainer: document.getElementById('steps-container'),
            previewContainer: document.getElementById('preview-container'),
            historyList: document.getElementById('history-list'),
            connectionDot: document.getElementById('connection-dot'),
            connectionText: document.getElementById('connection-text'),
        };

        this.stepIcons = {
            pending: '○',
            in_progress: '◐',
            completed: '✓',
            failed: '✗',
            skipped: '⊘',
        };

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.fetchInitialStatus();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}`;

        this.socket = io(wsUrl + '/progress', {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: Infinity,
        });

        this.socket.on('connect', () => {
            this.connected = true;
            this.updateConnectionStatus(true);
            console.log('Connected to progress server');
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            this.updateConnectionStatus(false);
            console.log('Disconnected from progress server');
        });

        this.socket.on('progress_update', (data) => {
            this.handleProgressUpdate(data);
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.updateConnectionStatus(false);
        });
    }

    fetchInitialStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => this.handleProgressUpdate(data))
            .catch(error => console.error('Error fetching status:', error));
    }

    updateConnectionStatus(connected) {
        const { connectionDot, connectionText } = this.elements;

        if (connected) {
            connectionDot.classList.add('connected');
            connectionDot.classList.remove('disconnected');
            connectionText.textContent = 'Connected';
        } else {
            connectionDot.classList.remove('connected');
            connectionDot.classList.add('disconnected');
            connectionText.textContent = 'Disconnected - Reconnecting...';
        }
    }

    handleProgressUpdate(data) {
        this.currentJob = data.current_job;
        this.jobHistory = data.job_history || [];

        this.renderCurrentJob();
        this.renderHistory();
    }

    renderCurrentJob() {
        const { noJob, jobInfo, jobSubreddit, jobTitle, jobStatusBadge,
            overallProgressFill, overallProgressText, stepsContainer, previewContainer } = this.elements;

        if (!this.currentJob) {
            noJob.classList.remove('hidden');
            jobInfo.classList.add('hidden');
            return;
        }

        noJob.classList.add('hidden');
        jobInfo.classList.remove('hidden');

        // Update job info
        jobSubreddit.textContent = `r/${this.currentJob.subreddit}`;
        jobTitle.textContent = this.currentJob.title;

        // Update status badge
        jobStatusBadge.textContent = this.formatStatus(this.currentJob.status);
        jobStatusBadge.className = `status-badge ${this.currentJob.status}`;

        // Update overall progress
        const progress = this.currentJob.overall_progress || 0;
        overallProgressFill.style.width = `${progress}%`;
        overallProgressText.textContent = `${Math.round(progress)}%`;

        // Render steps
        this.renderSteps(stepsContainer, this.currentJob.steps);

        // Update preview
        this.updatePreview(previewContainer, this.currentJob.steps);
    }

    renderSteps(container, steps) {
        container.innerHTML = '';

        steps.forEach((step, index) => {
            const stepEl = document.createElement('div');
            stepEl.className = `step ${this.getStepClass(step.status)}`;

            const icon = this.getStepIcon(step.status);
            const isActive = step.status === 'in_progress';

            stepEl.innerHTML = `
                <div class="step-icon">
                    ${isActive ? '<div class="spinner"></div>' : icon}
                </div>
                <div class="step-content">
                    <div class="step-name">${step.name}</div>
                    <div class="step-description">${step.description}</div>
                    ${step.message ? `<div class="step-message">${step.message}</div>` : ''}
                </div>
                ${step.status === 'in_progress' ? `
                    <div class="step-progress">
                        <div class="step-progress-bar">
                            <div class="step-progress-fill" style="width: ${step.progress}%"></div>
                        </div>
                        <div class="step-progress-text">${Math.round(step.progress)}%</div>
                    </div>
                ` : ''}
            `;

            container.appendChild(stepEl);
        });
    }

    getStepClass(status) {
        const classMap = {
            pending: 'pending',
            in_progress: 'active',
            completed: 'completed',
            failed: 'failed',
            skipped: 'skipped',
        };
        return classMap[status] || 'pending';
    }

    getStepIcon(status) {
        return this.stepIcons[status] || this.stepIcons.pending;
    }

    formatStatus(status) {
        const statusMap = {
            pending: 'Pending',
            in_progress: 'In Progress',
            completed: 'Completed',
            failed: 'Failed',
            skipped: 'Skipped',
        };
        return statusMap[status] || status;
    }

    updatePreview(container, steps) {
        // Find the latest step with a preview
        let previewPath = null;
        for (let i = steps.length - 1; i >= 0; i--) {
            if (steps[i].preview_path) {
                previewPath = steps[i].preview_path;
                break;
            }
        }

        if (!previewPath) {
            container.innerHTML = `
                <div class="preview-placeholder">
                    <p>Preview will appear here during processing</p>
                </div>
            `;
            return;
        }

        // Determine if it's an image or video
        const extension = previewPath.split('.').pop().toLowerCase();
        const isVideo = ['mp4', 'webm', 'mov'].includes(extension);

        if (isVideo) {
            container.innerHTML = `
                <video class="preview-video" controls autoplay muted loop>
                    <source src="${previewPath}" type="video/${extension}">
                    Your browser does not support video playback.
                </video>
            `;
        } else {
            container.innerHTML = `
                <img class="preview-image" src="${previewPath}" alt="Preview">
            `;
        }
    }

    renderHistory() {
        const { historyList } = this.elements;

        if (!this.jobHistory || this.jobHistory.length === 0) {
            historyList.innerHTML = '<p class="no-history">No completed jobs yet</p>';
            return;
        }

        historyList.innerHTML = '';

        // Show most recent first
        const sortedHistory = [...this.jobHistory].reverse();

        sortedHistory.forEach(job => {
            const item = document.createElement('div');
            item.className = 'history-item';

            const duration = job.completed_at && job.created_at
                ? this.formatDuration(job.completed_at - job.created_at)
                : 'N/A';

            const statusClass = job.status === 'completed' ? 'completed' : 'failed';

            item.innerHTML = `
                <div class="step-icon" style="background: var(--${job.status === 'completed' ? 'success' : 'error'}); color: white;">
                    ${job.status === 'completed' ? '✓' : '✗'}
                </div>
                <div style="flex: 1; min-width: 0;">
                    <div class="subreddit">r/${job.subreddit}</div>
                    <div class="title">${job.title}</div>
                    <div class="meta">
                        ${this.formatDate(job.created_at)} • ${duration}
                        ${job.error ? `• <span style="color: var(--error);">${job.error}</span>` : ''}
                    </div>
                </div>
                <div class="actions">
                    ${job.output_path ? `
                        <a href="${job.output_path}" class="btn btn-primary" target="_blank">
                            View Video
                        </a>
                    ` : ''}
                </div>
            `;

            historyList.appendChild(item);
        });
    }

    formatDuration(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.round(seconds % 60);
            return `${mins}m ${secs}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${mins}m`;
        }
    }

    formatDate(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleString();
    }
}

// Initialize the progress tracker when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.progressTracker = new ProgressTracker();
});
