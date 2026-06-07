class Atom2Socket {
    constructor(userId, handlers) {
        this.userId = userId;
        this.handlers = handlers || {};
        this.socket = null;
        this.reconnectDelay = 3000;
        this.connect();
    }

    connect() {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${proto}://${window.location.host}/ws/dashboard/`;
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('Atom2 WebSocket connected');
        };

        this.socket.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                this.dispatch(data);
            } catch (err) {
                console.error('WebSocket message error:', err);
            }
        };

        this.socket.onclose = () => {
            console.log('WebSocket closed — reconnecting...');
            setTimeout(() => this.connect(), this.reconnectDelay);
        };

        this.socket.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    }

    dispatch(data) {
        if (data.vm_id && this.handlers.onVMStatus) {
            this.handlers.onVMStatus(data);
        }
        if (data.deployment_status && this.handlers.onDeploymentStatus) {
            this.handlers.onDeploymentStatus(data);
        }
    }

    close() {
        if (this.socket) {
            this.socket.close();
        }
    }
}