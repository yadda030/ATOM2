document.addEventListener('DOMContentLoaded', function() {
    const sdnData = document.getElementById('sdn-config');

    let SDN_ZONES = [];
    let SDN_VNETS = [];

    try {
        SDN_ZONES = JSON.parse(sdnData.dataset.zones || '[]');
    } catch(e) {
        SDN_ZONES = [];
    }

    try {
        SDN_VNETS = JSON.parse(sdnData.dataset.vnets || '[]');
    } catch(e) {
        SDN_VNETS = [];
    }

    const zoneInput = document.getElementById('sdn-zone-input');
    const vnetInput = document.getElementById('sdn-vnet-input');

    if (SDN_ZONES.length > 0 && zoneInput) {
        const select = document.createElement('select');
        select.className = 'form-input';
        select.name = 'proxmox_sdn_zone';
        select.innerHTML = '<option value="">Select zone</option>' +
            SDN_ZONES.map(z => `<option value="${z.zone}">${z.zone}</option>`).join('');
        zoneInput.replaceWith(select);
    }

    if (SDN_VNETS.length > 0 && vnetInput) {
        const select = document.createElement('select');
        select.className = 'form-input';
        select.name = 'proxmox_sdn_vnet';
        select.innerHTML = '<option value="">Select vnet</option>' +
            SDN_VNETS.map(v => `<option value="${v.vnet}">${v.vnet}</option>`).join('');
        vnetInput.replaceWith(select);
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