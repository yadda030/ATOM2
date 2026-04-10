(function () {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/dashboard/`);

    socket.onmessage = function (e) {
        const data = JSON.parse(e.data);

        if (!data.deployment_id || data.deployment_id !== DEPLOYMENT_ID) return;

        // Handle deployment-level status update
        if (data.deployment_status) {
            const deploymentBadge = document.getElementById('deployment-badge');
            if (deploymentBadge) {
                deploymentBadge.className = `badge badge-${data.deployment_status}`;
                deploymentBadge.textContent = data.deployment_status_display;
            }
        }

        // Handle VM-level status update
        if (data.vm_id) {
            const badge = document.getElementById(`vm-badge-${data.vm_id}`);
            const actions = document.getElementById(`vm-actions-${data.vm_id}`);

            if (badge) {
                badge.className = `badge badge-${data.status}`;
                badge.textContent = data.status_display;
            }

            if (actions) {
                const startUrl = actions.dataset.startUrl;
                const stopUrl = actions.dataset.stopUrl;
                const csrf = actions.dataset.csrf;

                if (data.status === 'stopped') {
                    actions.innerHTML = `
                        <form method="post" action="${startUrl}" style="display:inline;">
                            <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                            <button type="submit" class="btn-sm btn-start">Start</button>
                        </form>`;
                } else if (data.status === 'running') {
                    actions.innerHTML = `
                        <form method="post" action="${stopUrl}" style="display:inline;">
                            <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                            <button type="submit" class="btn-sm btn-stop">Stop</button>
                        </form>`;
                } else {
                    // pending / error — no actions
                    actions.innerHTML = '';
                }
            }
        }
    };

    socket.onclose = function () {
        console.log('WS closed');
    };
})();