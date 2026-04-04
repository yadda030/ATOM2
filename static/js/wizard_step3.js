document.addEventListener('DOMContentLoaded', function() {
    const config = document.getElementById('vm-config');
    const PROXMOX_NODES = JSON.parse(config.dataset.nodes);
    const PROXMOX_TEMPLATES = JSON.parse(config.dataset.templates);

    const nodeSelect = document.getElementById('node-select');

    // Populate node select
    if (PROXMOX_NODES.length > 0 && nodeSelect) {
        nodeSelect.innerHTML = `<option value="">Select node</option>` +
            PROXMOX_NODES.map(n => `<option value="${n}">${n}</option>`).join('');

        nodeSelect.addEventListener('change', function() {
            updateTemplateSelect(this.value);
        });
    }

    function updateTemplateSelect(node) {
        const templateInput = document.getElementById('template-id-input');
        if (!templateInput) return;

        const templates = PROXMOX_TEMPLATES[node] || [];
        if (templates.length > 0) {
            const select = document.createElement('select');
            select.className = 'form-input';
            select.name = 'proxmox_template_id';
            select.id = 'template-id-input';
            select.required = true;
            select.innerHTML = `<option value="">Select template</option>` +
                templates.map(t => `<option value="${t.vmid}">${t.name} (VMID ${t.vmid})</option>`).join('');
            templateInput.replaceWith(select);
        } else {
            const input = document.createElement('input');
            input.className = 'form-input';
            input.type = 'text';
            input.name = 'proxmox_template_id';
            input.id = 'template-id-input';
            input.placeholder = 'Enter VMID manually';
            input.required = true;
            templateInput.replaceWith(input);
        }
    }

    window.toggleVMForm = function() {
        const form = document.getElementById('add-vm-form');
        const btn = document.getElementById('add-vm-btn');
        const visible = form.style.display !== 'none';
        form.style.display = visible ? 'none' : 'block';
        btn.style.display = visible ? 'block' : 'none';
    }
});