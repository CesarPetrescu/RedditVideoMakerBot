/**
 * Reddit Video Maker Bot - Shared JavaScript Utilities
 */

// Show notification toast
function showNotification(message, type = 'info') {
    const notif = document.createElement('div');
    notif.className = `notification ${type}`;
    notif.textContent = message;
    document.body.appendChild(notif);
    setTimeout(() => {
        notif.style.opacity = '0';
        notif.style.transform = 'translateY(20px)';
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

// Format file size
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Format duration in seconds to mm:ss
function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Format ISO date string to readable format
function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Debounce function for search inputs
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Escape HTML to prevent XSS
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Copy text to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success');
    } catch (err) {
        showNotification('Failed to copy', 'error');
    }
}

// API helper functions
const api = {
    get: async (url) => {
        const response = await fetch(url);
        return response.json();
    },

    post: async (url, data) => {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return response.json();
    },

    delete: async (url) => {
        const response = await fetch(url, { method: 'DELETE' });
        return response.json();
    },

    upload: async (url, file, onProgress) => {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const formData = new FormData();
            formData.append('file', file);

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    onProgress((e.loaded / e.total) * 100);
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error(xhr.statusText));
                }
            });

            xhr.addEventListener('error', () => reject(new Error('Upload failed')));
            xhr.open('POST', url);
            xhr.send(formData);
        });
    }
};

// WebSocket connection manager for progress updates
class ProgressSocket {
    constructor(namespace = '/progress') {
        this.socket = null;
        this.namespace = namespace;
        this.callbacks = [];
    }

    connect() {
        if (typeof io !== 'undefined') {
            this.socket = io(this.namespace);

            this.socket.on('connect', () => {
                console.log('Connected to progress socket');
            });

            this.socket.on('disconnect', () => {
                console.log('Disconnected from progress socket');
            });

            this.socket.on('progress_update', (data) => {
                this.callbacks.forEach(cb => cb(data));
            });
        }
    }

    onUpdate(callback) {
        this.callbacks.push(callback);
    }

    requestStatus() {
        if (this.socket) {
            this.socket.emit('request_status');
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Export for use in other scripts
window.showNotification = showNotification;
window.formatBytes = formatBytes;
window.formatDuration = formatDuration;
window.formatDate = formatDate;
window.debounce = debounce;
window.escapeHtml = escapeHtml;
window.copyToClipboard = copyToClipboard;
window.api = api;
window.ProgressSocket = ProgressSocket;
