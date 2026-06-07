"""
Network diagram layout engine for Atom2 — Swimlane edition.

Layout hierarchy:
  Network band  — one horizontal band per RangeTemplateNetwork / RangeNetwork
    VLAN sub-row  — one sub-row per distinct VLAN tag within the band
                    (plus one "Untagged" sub-row for NICs with no tag)
      VM card     — one card per VM per (network, vlan) combination
                    Multi-homed VMs appear once per band they belong to,
                    linked by a dashed vertical connector line.

Edges:
  Solid horizontal lines connect VMs within the same network + VLAN sub-row.
  Dashed vertical lines link the same VM across different bands/sub-rows.
"""

# ── Constants ────────────────────────────────────────────────────────────────

LEFT_LABEL_W    = 64      # width of the left label column
COL_W           = 165     # width of each VM card column (including gap)
VM_W            = 152     # VM card width
VM_H            = 52      # VM card height
VM_GAP          = 12      # horizontal gap between VM cards
VM_PAD_TOP      = 24      # vertical padding above first card in sub-row
VM_PAD_BOT      = 10      # vertical padding below last card in sub-row

SUBROW_H        = VM_H + VM_PAD_TOP + VM_PAD_BOT   # height of one VLAN sub-row
NET_DIVIDER     = 1       # px of divider between networks

SVG_MIN_W       = 700
SVG_PAD_TOP     = 8
SVG_PAD_BOT     = 16

# ── Colour maps ──────────────────────────────────────────────────────────────

NET_COLORS = [
    {'band': '#EEF6FC', 'stroke': '#378add', 'label': '#185fa5',
     'vlan_div': '#c5dff5', 'edge': '#378add'},

    {'band': '#EAF7F2', 'stroke': '#1D9E75', 'label': '#0F6E56',
     'vlan_div': '#b5e8d5', 'edge': '#1D9E75'},

    {'band': '#FBF3E4', 'stroke': '#BA7517', 'label': '#854F0B',
     'vlan_div': '#f0d5a0', 'edge': '#BA7517'},

    {'band': '#F2F1FE', 'stroke': '#7F77DD', 'label': '#534AB7',
     'vlan_div': '#cccaf5', 'edge': '#7F77DD'},

    {'band': '#FDF0EC', 'stroke': '#D85A30', 'label': '#993C1D',
     'vlan_div': '#f5c9b8', 'edge': '#D85A30'},
]

STATUS_COLORS = {
    'running': {'fill': '#EAF3DE', 'stroke': '#3B6D11', 'text': '#27500A'},
    'stopped': {'fill': '#F1EFE8', 'stroke': '#888780', 'text': '#444441'},
    'error':   {'fill': '#FCEBEB', 'stroke': '#A32D2D', 'text': '#501313'},
    'pending': {'fill': '#E6F1FB', 'stroke': '#378add', 'text': '#0C447C'},
}

DEFAULT_VM_COLOR = {'fill': '#F5F4F0', 'stroke': '#B4B2A9', 'text': '#444441'}


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
    # Strip deployment name prefix from VM display names
    prefix = deployment.name + '-'
    for vm in vms:
        vm.display_name = vm.name[len(prefix):] if vm.name.startswith(prefix) else vm.name
    return _build(networks, vms, mode='deployment')


# ── Core ─────────────────────────────────────────────────────────────────────

def _build(networks, vms, mode):
    # ── 1. Resolve NIC memberships ───────────────────────────────────────────
    vm_nics = {}
    for vm in vms:
        vm_nics[vm.pk] = _get_nics(vm, networks, mode)

    # ── 2. Group VMs into (net_pk, vlan_tag) buckets ─────────────────────────
    buckets = {}
    unconnected = []

    for vm in vms:
        nics = vm_nics[vm.pk]
        if not nics:
            unconnected.append(vm)
            continue
        seen = set()
        for net_pk, vlan in nics:
            key = (net_pk, vlan)
            if key in seen:
                continue
            seen.add(key)
            buckets.setdefault(key, []).append(vm)

    # ── 3. Build per-network VLAN lists ──────────────────────────────────────
    net_vlans = {}
    for net in networks:
        vlans_seen = set()
        for (npk, vlan) in buckets.keys():
            if npk == net.pk:
                vlans_seen.add(vlan)
        net_vlans[net.pk] = sorted(vlans_seen, key=lambda v: (v is None, v or 0))

    # ── 4. Assign column positions ───────────────────────────────────────────
    vm_col = {}
    next_col = 0

    for (net_pk, vlan), row_vms in buckets.items():
        for vm in row_vms:
            if vm.pk not in vm_col:
                vm_col[vm.pk] = next_col
                next_col += 1

    for vm in unconnected:
        if vm.pk not in vm_col:
            vm_col[vm.pk] = next_col
            next_col += 1

    max_col = max(next_col, 1)

    # ── 5. Compute SVG width ─────────────────────────────────────────────────
    svg_w = max(SVG_MIN_W, LEFT_LABEL_W + max_col * COL_W + VM_GAP)

    # ── 6. Build output lists ─────────────────────────────────────────────────
    zones_out    = []
    vlan_rects   = []
    nodes_out    = []
    edges_out    = []
    legend       = []
    vm_centers   = {}   # vm.pk → list of (cx, cy)

    y_cursor = SVG_PAD_TOP

    for net_idx, net in enumerate(networks):
        color = NET_COLORS[net_idx % len(NET_COLORS)]
        vlans = net_vlans.get(net.pk, [])
        if not vlans:
            vlans = [None]

        band_h = len(vlans) * SUBROW_H
        band_y = y_cursor

        zones_out.append({
            'x': 0, 'y': band_y, 'w': svg_w, 'h': band_h,
            'label': net.name,
            'sublabel': _net_sublabel(net),
            'stroke': color['stroke'],
            'label_color': color['label'],
            'band_color': color['band'],
        })

        for vlan_idx, vlan in enumerate(vlans):
            subrow_y = band_y + vlan_idx * SUBROW_H
            vlan_label = f'VLAN {vlan}' if vlan is not None else 'Untagged'

            if vlan_idx > 0:
                vlan_rects.append({
                    'x1': LEFT_LABEL_W, 'y1': subrow_y,
                    'x2': svg_w,        'y2': subrow_y,
                    'color': color['vlan_div'],
                    'label': vlan_label,
                    'label_x': LEFT_LABEL_W + 4,
                    'label_y': subrow_y + 12,
                    'label_color': color['label'],
                    'is_divider': True,
                })
            else:
                vlan_rects.append({
                    'x1': 0, 'y1': 0, 'x2': 0, 'y2': 0,
                    'color': 'none',
                    'label': vlan_label,
                    'label_x': LEFT_LABEL_W + 4,
                    'label_y': subrow_y + 12,
                    'label_color': color['label'],
                    'is_divider': False,
                })

            row_vms = buckets.get((net.pk, vlan), [])
            card_y = subrow_y + VM_PAD_TOP
            card_cx_list = []

            for vm in row_vms:
                col = vm_col.get(vm.pk, 0)
                card_x = LEFT_LABEL_W + col * COL_W
                status = _vm_status(vm, mode)
                ip     = _vm_ip(vm, mode)
                vc     = _vm_color(status)
                is_multihomed = len(vm_nics.get(vm.pk, [])) > 1
                net_dots = _net_dots(vm, networks, vm_nics)

                nodes_out.append({
                    'id':         vm.pk,
                    'label':      getattr(vm, 'display_name', vm.name),
                    'ip':         ip,
                    'x':          card_x,
                    'y':          card_y,
                    'w':          VM_W,
                    'h':          VM_H,
                    'fill':       vc['fill'],
                    'stroke':     vc['stroke'],
                    'text_color': vc['text'],
                    'status':     status or '',
                    'multihomed': is_multihomed,
                    'net_dots':   net_dots,
                })

                cx = card_x + VM_W // 2
                cy = card_y + VM_H // 2
                vm_centers.setdefault(vm.pk, []).append((cx, cy))
                card_cx_list.append((cx, cy))

            # Horizontal edges within sub-row
            for i in range(len(card_cx_list) - 1):
                x1, y1 = card_cx_list[i]
                x2, y2 = card_cx_list[i + 1]
                edges_out.append({
                    'x1': x1, 'y1': y1,
                    'x2': x2, 'y2': y2,
                    'color': color['edge'],
                    'dashed': False,
                })

        y_cursor += band_h + NET_DIVIDER

    # ── Unconnected VMs ───────────────────────────────────────────────────────
    unconnected_zone = None
    if unconnected:
        band_y = y_cursor
        band_h = SUBROW_H
        uc = {'band': '#F5F4F0', 'stroke': '#B4B2A9',
              'label': '#5F5E5A', 'edge': '#B4B2A9'}
        unconnected_zone = {
            'x': 0, 'y': band_y, 'w': svg_w, 'h': band_h,
            'label': 'No network', 'sublabel': '',
            'stroke': uc['stroke'], 'label_color': uc['label'],
            'band_color': uc['band'],
        }
        card_y = band_y + VM_PAD_TOP
        card_cx_list = []
        for vm in unconnected:
            col = vm_col.get(vm.pk, 0)
            card_x = LEFT_LABEL_W + col * COL_W
            status = _vm_status(vm, mode)
            vc = _vm_color(status)
            nodes_out.append({
                'id': vm.pk, 'label': getattr(vm, 'display_name', vm.name), 'ip': _vm_ip(vm, mode),
                'x': card_x, 'y': card_y, 'w': VM_W, 'h': VM_H,
                'fill': vc['fill'], 'stroke': vc['stroke'],
                'text_color': vc['text'], 'status': status or '',
                'multihomed': False, 'net_dots': [],
            })
            cx = card_x + VM_W // 2
            cy = card_y + VM_H // 2
            vm_centers.setdefault(vm.pk, []).append((cx, cy))
            card_cx_list.append((cx, cy))
        for i in range(len(card_cx_list) - 1):
            x1, y1 = card_cx_list[i]
            x2, y2 = card_cx_list[i + 1]
            edges_out.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                               'color': uc['edge'], 'dashed': False})
        y_cursor += band_h

    # ── Vertical dashed connectors for multi-homed VMs ───────────────────────
    for vm_pk, centers in vm_centers.items():
        if len(centers) < 2:
            continue
        sorted_c = sorted(centers, key=lambda c: c[1])
        for i in range(len(sorted_c) - 1):
            x1, y1 = sorted_c[i]
            x2, y2 = sorted_c[i + 1]
            edges_out.append({
                'x1': x1, 'y1': y1 + VM_H // 2,
                'x2': x2, 'y2': y2 - VM_H // 2,
                'color': '#aaaaaa',
                'dashed': True,
            })

    # ── Legend ────────────────────────────────────────────────────────────────
    for i, net in enumerate(networks):
        c = NET_COLORS[i % len(NET_COLORS)]
        legend.append({'label': net.name, 'color': c['edge'], 'square': False})
    if mode == 'deployment':
        for s, c in STATUS_COLORS.items():
            legend.append({'label': s.capitalize(), 'color': c['stroke'], 'square': True})

    svg_h = y_cursor + SVG_PAD_BOT

    return {
        'svg_width':        round(svg_w),
        'svg_height':       round(svg_h),
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
    net_pks = {n.pk for n in networks}
    result  = []

    if mode == 'template':
        ifaces = sorted(vm.network_interfaces.all(), key=lambda i: i.interface_index)
        for iface in ifaces:
            if iface.network_id and iface.network_id in net_pks:
                result.append((iface.network_id, getattr(iface, 'vlan_tag', None)))

    else:  # deployment
        if not vm.vm_template:
            return []
        ifaces = sorted(
            vm.vm_template.network_interfaces.all(),
            key=lambda i: i.interface_index,
        )

        tmpl_to_deploy = {}
        for dn in networks:
            if hasattr(dn, 'copied_from_id') and dn.copied_from_id:
                tmpl_to_deploy[dn.copied_from_id] = dn.pk

        if not tmpl_to_deploy:
            deploy_by_vnet = {}
            deploy_by_name = {}
            for dn in networks:
                if hasattr(dn, 'proxmox_sdn_vnet') and dn.proxmox_sdn_vnet:
                    deploy_by_vnet[dn.proxmox_sdn_vnet] = dn.pk
                if hasattr(dn, 'name') and dn.name:
                    deploy_by_name[dn.name] = dn.pk

            for iface in ifaces:
                vlan = getattr(iface, 'vlan_tag', None)
                if iface.network_id and iface.network:
                    deploy_pk = (
                        deploy_by_vnet.get(iface.network.proxmox_sdn_vnet) or
                        deploy_by_name.get(iface.network.name)
                    )
                    if deploy_pk:
                        result.append((deploy_pk, vlan))
                elif iface.manual_vnet:
                    deploy_pk = deploy_by_vnet.get(iface.manual_vnet)
                    if deploy_pk:
                        result.append((deploy_pk, vlan))
        else:
            for iface in ifaces:
                vlan = getattr(iface, 'vlan_tag', None)
                if iface.network_id:
                    deploy_pk = tmpl_to_deploy.get(iface.network_id)
                    if deploy_pk and deploy_pk in net_pks:
                        result.append((deploy_pk, vlan))

    return result


def _net_dots(vm, networks, vm_nics):
    net_map = {n.pk: n for n in networks}
    net_color_map = {n.pk: NET_COLORS[i % len(NET_COLORS)]
                     for i, n in enumerate(networks)}
    seen = set()
    dots = []
    for net_pk, vlan in vm_nics.get(vm.pk, []):
        if net_pk in seen:
            continue
        seen.add(net_pk)
        net = net_map.get(net_pk)
        color = net_color_map.get(net_pk, {})
        dots.append({
            'color': color.get('edge', '#888'),
            'label': net.name if net else '',
        })
    return dots


def _net_sublabel(net):
    parts = []
    if getattr(net, 'subnet', None):
        parts.append(net.subnet)
    if getattr(net, 'proxmox_sdn_vnet', None):
        parts.append(net.proxmox_sdn_vnet)
    return ' · '.join(parts)


def _vm_status(vm, mode):
    return vm.status if mode == 'deployment' else None


def _vm_ip(vm, mode):
    if mode == 'deployment':
        try:
            return vm.config.ip_address or ''
        except Exception:
            return ''
    return ''


def _vm_color(status):
    if status and status in STATUS_COLORS:
        return STATUS_COLORS[status]
    return DEFAULT_VM_COLOR