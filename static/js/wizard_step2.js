document.addEventListener('DOMContentLoaded', function() {
    const config = document.getElementById('sdn-config');
    const SDN_ZONES = JSON.parse(config.dataset.zones);
    const SDN_VNETS = JSON.parse(config.dataset.vnets);

    const zoneInput = document.getElementById('sdn-zone-input');
    const vnetInput = document.getElementById('sdn-vnet-input');

    // Replace inputs with selects if Proxmox data available
    if (SDN_ZONES.length > 0 && zoneInput) {
        const select = document.createElement('select');
        select.className = 'form-input';
        select.name = 'proxmox_sdn_zone';
        select.innerHTML = `<option value="">Select zone</option>` +
            SDN_ZONES.map(z => `<option value="${z.zone}">${z.zone}</option>`).join('');
        zoneInput.replaceWith(select);
    }

    if (SDN_VNETS.length > 0 && vnetInput) {
        const select = document.createElement('select');
        select.className = 'form-input';
        select.name = 'proxmox_sdn_vnet';
        select.innerHTML = `<option value="">Select vnet</option>` +
            SDN_VNETS.map(v => `<option value="${v.vnet}">${v.vnet}</option>`).join('');
        vnetInput.replaceWith(select);
    }

    window.toggleAddForm = function() {
        const form = document.getElementById('add-network-form');
        const btn = document.getElementById('add-network-btn');
        const visible = form.style.display !== 'none';
        form.style.display = visible ? 'none' : 'block';
        btn.style.display = visible ? 'block' : 'none';
    }
});