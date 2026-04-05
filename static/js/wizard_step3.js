document.addEventListener('DOMContentLoaded', function() {
    const vmData = document.getElementById('vm-config');

    let PROXMOX_NODES = [];
    let PROXMOX_TEMPLATES = {};

    try {
        PROXMOX_NODES = JSON.parse(vmData.dataset.nodes || '[]');
    } catch(e) {
        PROXMOX_NODES = [];
    }

    try {
        PROXMOX_TEMPLATES = JSON.parse(vmData.dataset.templates || '{}');
    } catch(e) {
        PROXMOX_TEMPLATES = {};
    }

    const nodeSelect = document.getElementById('node-select');
    const templateInput = document.getElementById('template-id-input');

    if (PROXMOX_NODES.length > 0 && nodeSelect) {
        nodeSelect.innerHTML = '<option value="">Select node</option>' +
            PROXMOX_NODES.map(n => `<option value="${n}">${n}</option>`).join('');

        nodeSelect.addEventListener('change', function() {
            updateTemplateOptions(this.value);
        });
    }

    function updateTemplateOptions(node) {
        const templates = PROXMOX_TEMPLATES[node] || [];
        const el = document.getElementById('template-id-input');
        if (!el) return;

        if (templates.length > 0) {
            const select = document.createElement('select');
            select.className = 'form-input';
            select.name = 'proxmox_template_id';
            select.id = 'template-id-input';
            select.required = true;
            select.innerHTML = '<option value="">Select template</option>' +
                templates.map(t => `<option value="${t.vmid}">${t.name} (VMID ${t.vmid})</option>`).join('');
            el.replaceWith(select);
        } else {
            const input = document.createElement('input');
            input.className = 'form-input';
            input.type = 'number';
            input.name = 'proxmox_template_id';
            input.id = 'template-id-input';
            input.placeholder = 'Enter VMID manually';
            input.required = true;
            el.replaceWith(input);
        }
    }
});

function toggleEditForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    const isHidden = form.style.display === 'none';
    form.style.display = isHidden ? 'block' : 'none';
}

function toggleAddForm(formId, btnId) {
    const form = document.getElementById(formId);
    const btn = btnId ? document.getElementById(btnId) : null;
    if (!form) return;
    const isHidden = form.style.display === 'none';
    form.style.display = isHidden ? 'block' : 'none';
    if (btn) btn.style.display = isHidden ? 'none' : 'block';
}