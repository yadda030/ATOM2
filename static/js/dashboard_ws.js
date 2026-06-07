document.addEventListener('DOMContentLoaded', function() {
    const config = document.getElementById('dashboard-ws-config');
    if (!config) return;

    const userId = config.dataset.userId;

    const STATUS_CLASSES = {
        'running':    'badge-running',
        'stopped':    'badge-stopped',
        'error':      'badge-error',
        'pending':    'badge-pending',
        'deploying':  'badge-deploying',
        'fragmented': 'badge-fragmented',
    };

    new Atom2Socket(userId, {
        onVMStatus: function(data) {
            const pill = document.getElementById(`vm-pill-${data.vm_id}`);
            if (pill) {
                const dot = pill.querySelector('.status-dot');
                if (dot) {
                    dot.className = `status-dot dot-${data.status}`;
                }
                const statusText = pill.querySelector('.vm-status');
                if (statusText) {
                    statusText.className = `vm-status ${data.status}`;
                    statusText.innerHTML = `<span class="status-dot dot-${data.status}"></span>${data.status_display || data.status}`;
                }
            }
        },

        onDeploymentStatus: function(data) {
            const badge = document.getElementById(`deployment-badge-${data.deployment_id}`);
            if (badge) {
                badge.className = `badge ${STATUS_CLASSES[data.deployment_status] || ''}`;
                badge.textContent = data.deployment_status_display || data.deployment_status;
            }
        }
    });
});