document.addEventListener('DOMContentLoaded', function() {
    const config = document.getElementById('range-detail-config');
    if (!config) return;

    const userId = config.dataset.userId;
    const deploymentId = config.dataset.deploymentId;

    const STATUS_CLASSES = {
        'running': { badge: 'badge-running', text: 'Running' },
        'stopped': { badge: 'badge-stopped', text: 'Stopped' },
        'error':   { badge: 'badge-error',   text: 'Error' },
        'pending': { badge: 'badge-pending', text: 'Pending' },
    };

    new Atom2Socket(userId, {
        onVMStatus: function(data) {
            if (String(data.deployment_id) !== String(deploymentId)) return;

            const vmCard = document.getElementById(`vm-card-${data.vm_id}`);
            if (vmCard) {
                const badge = vmCard.querySelector('.badge');
                const statusInfo = STATUS_CLASSES[data.status] || {};

                if (badge) {
                    badge.className = `badge ${statusInfo.badge || ''}`;
                    badge.textContent = data.status_display || data.status;
                }

                const startBtn = vmCard.querySelector('.vm-start-btn');
                const stopBtn  = vmCard.querySelector('.vm-stop-btn');
                if (startBtn) startBtn.style.display = data.status === 'stopped' ? 'inline' : 'none';
                if (stopBtn)  stopBtn.style.display  = data.status === 'running'  ? 'inline' : 'none';
            }
        },

        onDeploymentStatus: function(data) {
            if (String(data.deployment_id) !== String(deploymentId)) return;

            const deployBadge = document.getElementById('deployment-status-badge');
            if (deployBadge) {
                const statusInfo = STATUS_CLASSES[data.deployment_status] || {};
                deployBadge.className = `badge ${statusInfo.badge || ''}`;
                deployBadge.textContent = data.deployment_status_display || data.deployment_status;
            }
        }
    });
});