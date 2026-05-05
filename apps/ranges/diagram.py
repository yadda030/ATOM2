"""
Network diagram layout engine for Atom2.

Hierarchy:
  Outer zone  — one per RangeTemplateNetwork / RangeNetwork
    VLAN group  — one per distinct VLAN tag used on NICs in this zone
                  (plus one "Untagged" group for NICs with no tag)
      VM card   — name + IP (deployment mode) or name only (template mode)

VMs with NICs on multiple networks appear in each relevant zone/VLAN group.
Dual-homed VMs (NICs on 2+ different outer zones) are placed on the boundary.
"""

# ── Constants ────────────────────────────────────────────────────────────────

PADDING_OUTER   = 24
ZONE_TOP        = 24
ZONE_GAP        = 16      # horizontal gap between outer zones

ZONE_HEADER_H   = 36      # outer zone label area
VLAN_HEADER_H   = 24      # inner VLAN group label area
VLAN_PAD_H      = 10      # horizontal padding inside VLAN group
VLAN_PAD_V      = 10      # vertical padding inside VLAN group
VLAN_GAP        = 10      # vertical gap between VLAN groups
ZONE_PAD_H      = 12      # horizontal padding inside outer zone
ZONE_PAD_BOT    = 16      # bottom padding inside outer zone

VM_W            = 148
VM_H            = 42
VM_GAP          = 10      # vertical gap between VM cards

MIN_VLAN_W      = VM_W + VLAN_PAD_H * 2
MIN_ZONE_W      = MIN_VLAN_W + ZONE_PAD_H * 2

SVG_MIN_WIDTH   = 680

# ── Colour maps ──────────────────────────────────────────────────────────────

ZONE_COLORS = [
    {'zone_stroke': '#378add', 'zone_fill': 'none',
     'vlan_stroke': '#378add', 'vlan_fill': '#EEF6FC',
     'vm_fill': '#E6F1FB',    'vm_stroke': '#378add',
     'text': '#0C447C',       'sub': '#185fa5', 'label': '#185fa5'},

    {'zone_stroke': '#1D9E75', 'zone_fill': 'none',
     'vlan_stroke': '#1D9E75', 'vlan_fill': '#EAF7F2',
     'vm_fill': '#E1F5EE',    'vm_stroke': '#1D9E75',
     'text': '#085041',       'sub': '#0F6E56', 'label': '#0F6E56'},

    {'zone_stroke': '#BA7517', 'zone_fill': 'none',
     'vlan_stroke': '#BA7517', 'vlan_fill': '#FBF3E4',
     'vm_fill': '#FAEEDA',    'vm_stroke': '#BA7517',
     'text': '#412402',       'sub': '#854F0B', 'label': '#854F0B'},

    {'zone_stroke': '#7F77DD', 'zone_fill': 'none',
     'vlan_stroke': '#7F77DD', 'vlan_fill': '#F2F1FE',
     'vm_fill': '#EEEDFE',    'vm_stroke': '#7F77DD',
     'text': '#26215C',       'sub': '#534AB7', 'label': '#534AB7'},

    {'zone_stroke': '#D85A30', 'zone_fill': 'none',
     'vlan_stroke': '#D85A30', 'vlan_fill': '#FDF0EC',
     'vm_fill': '#FAECE7',    'vm_stroke': '#D85A30',
     'text': '#4A1B0C',       'sub': '#993C1D', 'label': '#993C1D'},
]

STATUS_COLORS = {
    'running': {'fill': '#EAF3DE', 'stroke': '#3B6D11', 'text': '#27500A'},
    'stopped': {'fill': '#F1EFE8', 'stroke': '#888780', 'text': '#444441'},
    'error':   {'fill': '#FCEBEB', 'stroke': '#A32D2D', 'text': '#501313'},
    'pending': {'fill': '#E6F1FB', 'stroke': '#378add', 'text': '#0C447C'},
}

UNCONNECTED_COLOR = {
    'zone_stroke': '#B4B2A9', 'vlan_stroke': '#B4B2A9', 'vlan_fill': '#F5F4F0',
    'vm_fill': '#F1EFE8', 'vm_stroke': '#B4B2A9', 'text': '#444441', 'label': '#5F5E5A',
}


# ── Public entry points ──────────────────────────────────────────────────────

def build_template_diagram(template):
    networks = list(template.networks.all())
    vms = list(template.vm_templates.prefetch_related(
        'network_interfaces__network'
    ).all())
    return _build(networks, vms, mode='template')


def build_deployment_diagram(deployment):
    networks = list(deployment.networks.all())
    vms = list(
        deployment.vms
        .select_related('vm_template', 'config')
        .prefetch_related('vm_template__network_interfaces__network')
        .all()
    )
    return _build(networks, vms, mode='deployment')


# ── Core ─────────────────────────────────────────────────────────────────────

def _build(networks, vms, mode):
    net_color  = {n.pk: ZONE_COLORS[i % len(ZONE_COLORS)] for i, n in enumerate(networks)}
    net_index  = {n.pk: i for i, n in enumerate(networks)}

    # ── Gather NIC data per VM ───────────────────────────────────────────────
    # vm_nics[vm.pk] = list of (network_pk, vlan_tag or None)
    vm_nics = {}
    for vm in vms:
        vm_nics[vm.pk] = _get_nics(vm, networks, mode)

    # ── Build VLAN groups per network ────────────────────────────────────────
    # vlan_groups[net_pk][vlan_tag_or_None] = [vm, ...]
    vlan_groups = {n.pk: {} for n in networks}
    unconnected_vms = []

    for vm in vms:
        nics = vm_nics[vm.pk]
        if not nics:
            unconnected_vms.append(vm)
            continue
        seen_in_zone = {}   # net_pk → set of vlan_tags already placed
        for net_pk, vlan_tag in nics:
            if net_pk not in vlan_groups:
                continue
            key = vlan_tag  # None = untagged
            seen = seen_in_zone.setdefault(net_pk, set())
            if key in seen:
                continue    # don't duplicate within same zone/vlan
            seen.add(key)
            vlan_groups[net_pk].setdefault(key, []).append(vm)

    # ── Compute sizes ────────────────────────────────────────────────────────
    def vlan_group_height(vm_count):
        return VLAN_HEADER_H + VLAN_PAD_V + vm_count * VM_H + (vm_count - 1) * VM_GAP + VLAN_PAD_V

    def zone_height(net_pk):
        groups = vlan_groups[net_pk]
        if not groups:
            return ZONE_HEADER_H + vlan_group_height(0) + ZONE_PAD_BOT
        total = ZONE_HEADER_H
        for vms_in_group in groups.values():
            total += vlan_group_height(len(vms_in_group)) + VLAN_GAP
        total += ZONE_PAD_BOT
        return total

    def zone_width(_net_pk):
        return MIN_ZONE_W

    # ── Layout zones left-to-right ───────────────────────────────────────────
    zones_out   = []
    vlan_rects  = []   # rendered VLAN group boxes
    nodes_out   = []
    node_centers = {}  # vm_pk → list of (cx, cy) — one per placement

    x_cursor = PADDING_OUTER
    zone_bounds = {}   # net_pk → (x, y, w, h)

    for i, net in enumerate(networks):
        color = net_color[net.pk]
        w = zone_width(net.pk)
        h = zone_height(net.pk)
        zx, zy = x_cursor, ZONE_TOP

        zone_bounds[net.pk] = (zx, zy, w, h)

        sublabel = ''
        if hasattr(net, 'subnet') and net.subnet:
            sublabel = net.subnet
        if hasattr(net, 'proxmox_sdn_vnet') and net.proxmox_sdn_vnet:
            sublabel = (sublabel + ' · ' if sublabel else '') + net.proxmox_sdn_vnet

        zones_out.append({
            'x': zx, 'y': zy, 'w': w, 'h': h,
            'label': net.name,
            'sublabel': sublabel,
            'stroke': color['zone_stroke'],
            'label_color': color['label'],
        })

        # Place VLAN groups top-to-bottom inside zone
        vy = zy + ZONE_HEADER_H
        groups = vlan_groups[net.pk]
        sorted_keys = sorted(groups.keys(), key=lambda k: (k is None, k))

        for vlan_key in sorted_keys:
            vms_in_group = groups[vlan_key]
            gh = vlan_group_height(len(vms_in_group))
            gx = zx + ZONE_PAD_H
            gw = w - ZONE_PAD_H * 2

            vlan_label = f'VLAN {vlan_key}' if vlan_key is not None else 'Untagged'

            vlan_rects.append({
                'x': gx, 'y': vy, 'w': gw, 'h': gh,
                'label': vlan_label,
                'stroke': color['vlan_stroke'],
                'fill': color['vlan_fill'],
                'label_color': color['label'],
            })

            # Place VMs inside VLAN group
            vm_y = vy + VLAN_HEADER_H + VLAN_PAD_V
            vm_x = gx + VLAN_PAD_H
            for vm in vms_in_group:
                status  = _vm_status(vm, mode)
                ip      = _vm_ip(vm, mode)
                vc      = _vm_color(status, color)
                nodes_out.append({
                    'id':         vm.pk,
                    'label':      vm.name,
                    'ip':         ip,
                    'x':          round(vm_x),
                    'y':          round(vm_y),
                    'w':          VM_W,
                    'h':          VM_H,
                    'fill':       vc['fill'],
                    'stroke':     vc['stroke'],
                    'text_color': vc['text'],
                    'status':     status or '',
                })
                cx = vm_x + VM_W / 2
                cy = vm_y + VM_H / 2
                node_centers.setdefault(vm.pk, []).append((round(cx), round(cy)))
                vm_y += VM_H + VM_GAP

            vy += gh + VLAN_GAP

        x_cursor += w + ZONE_GAP

    # ── Unconnected zone ─────────────────────────────────────────────────────
    unconnected_zone = None
    if unconnected_vms:
        gh = vlan_group_height(len(unconnected_vms))
        w  = MIN_ZONE_W
        h  = ZONE_HEADER_H + gh + ZONE_PAD_BOT
        zx, zy = x_cursor, ZONE_TOP
        unconnected_zone = {
            'x': zx, 'y': zy, 'w': w, 'h': h,
            'label': 'No network', 'sublabel': '',
            'stroke': '#B4B2A9', 'label_color': '#5F5E5A',
        }
        vy = zy + ZONE_HEADER_H
        vlan_rects.append({
            'x': zx + ZONE_PAD_H, 'y': vy,
            'w': w - ZONE_PAD_H * 2, 'h': gh,
            'label': 'Untagged',
            'stroke': '#B4B2A9', 'fill': '#F5F4F0',
            'label_color': '#5F5E5A',
        })
        vm_y = vy + VLAN_HEADER_H + VLAN_PAD_V
        for vm in unconnected_vms:
            status = _vm_status(vm, mode)
            ip     = _vm_ip(vm, mode)
            vc     = _vm_color(status, UNCONNECTED_COLOR)
            nodes_out.append({
                'id': vm.pk, 'label': vm.name, 'ip': ip,
                'x': round(zx + ZONE_PAD_H + VLAN_PAD_H),
                'y': round(vm_y),
                'w': VM_W, 'h': VM_H,
                'fill': vc['fill'], 'stroke': vc['stroke'],
                'text_color': vc['text'], 'status': status or '',
            })
            node_centers.setdefault(vm.pk, []).append((
                round(zx + ZONE_PAD_H + VLAN_PAD_H + VM_W / 2),
                round(vm_y + VM_H / 2),
            ))
            vm_y += VM_H + VM_GAP
        x_cursor += w + ZONE_GAP

    # ── SVG dimensions ───────────────────────────────────────────────────────
    svg_width  = max(SVG_MIN_WIDTH, x_cursor - ZONE_GAP + PADDING_OUTER)
    all_heights = [z['h'] for z in zones_out]
    if unconnected_zone:
        all_heights.append(unconnected_zone['h'])
    svg_height = ZONE_TOP + (max(all_heights) if all_heights else 200) + 48

    # ── Edges ────────────────────────────────────────────────────────────────
    # Draw an edge between each pair of VM placements that share a network
    edges_out  = []
    seen_pairs = set()

    for i, vm_a in enumerate(vms):
        for vm_b in vms[i + 1:]:
            nics_a = set((npk, vt) for npk, vt in vm_nics.get(vm_a.pk, []))
            nics_b = set((npk, vt) for npk, vt in vm_nics.get(vm_b.pk, []))
            shared = nics_a & nics_b
            if not shared:
                continue
            pair = (min(vm_a.pk, vm_b.pk), max(vm_a.pk, vm_b.pk))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            centers_a = node_centers.get(vm_a.pk, [])
            centers_b = node_centers.get(vm_b.pk, [])
            if not centers_a or not centers_b:
                continue

            # Use the centres closest to each other
            cx1, cy1 = centers_a[0]
            cx2, cy2 = centers_b[0]

            shared_net_pk = next(iter(shared))[0]
            edge_color = net_color.get(shared_net_pk, ZONE_COLORS[0])['zone_stroke']

            edges_out.append({
                'x1': cx1, 'y1': cy1,
                'x2': cx2, 'y2': cy2,
                'color': edge_color,
            })

    # ── Legend ───────────────────────────────────────────────────────────────
    legend = []
    for net in networks:
        legend.append({
            'label': net.name,
            'color': net_color[net.pk]['zone_stroke'],
            'square': False,
        })
    if mode == 'deployment':
        for s, c in STATUS_COLORS.items():
            legend.append({'label': s.capitalize(), 'color': c['stroke'], 'square': True})

    return {
        'svg_width':        round(svg_width),
        'svg_height':       round(svg_height),
        'zones':            zones_out,
        'unconnected_zone': unconnected_zone,
        'vlan_rects':       vlan_rects,
        'nodes':            nodes_out,
        'edges':            edges_out,
        'legend':           legend,
        'mode':             mode,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_nics(vm, networks, mode):
    """
    Return list of (network_pk, vlan_tag_or_None) for each NIC on this VM,
    in interface_index order. Duplicate (net_pk, vlan) pairs are kept so a
    VM appears in each zone it belongs to.
    """
    net_pks = {n.pk for n in networks}
    result  = []

    if mode == 'template':
        ifaces = sorted(vm.network_interfaces.all(), key=lambda i: i.interface_index)
        for iface in ifaces:
            if iface.network_id and iface.network_id in net_pks:
                result.append((iface.network_id, iface.vlan_tag))

    else:  # deployment
        if not vm.vm_template:
            return []
        ifaces = sorted(
            vm.vm_template.network_interfaces.all(),
            key=lambda i: i.interface_index,
        )
        # Map template network pk → deployment network pk
        tmpl_to_deploy = {}
        for dn in networks:
            if hasattr(dn, 'copied_from_id') and dn.copied_from_id:
                tmpl_to_deploy[dn.copied_from_id] = dn.pk

        for iface in ifaces:
            if iface.network_id:
                deploy_pk = tmpl_to_deploy.get(iface.network_id)
                if deploy_pk and deploy_pk in net_pks:
                    result.append((deploy_pk, iface.vlan_tag))

    return result


def _vm_status(vm, mode):
    return vm.status if mode == 'deployment' else None


def _vm_ip(vm, mode):
    if mode == 'deployment':
        try:
            return vm.config.ip_address or ''
        except Exception:
            return ''
    return ''


def _vm_color(status, zone_color):
    if status and status in STATUS_COLORS:
        return STATUS_COLORS[status]
    return {
        'fill':   zone_color.get('vm_fill',   '#F1EFE8'),
        'stroke': zone_color.get('vm_stroke', '#B4B2A9'),
        'text':   zone_color.get('text',      '#444441'),
    }