"""
mermaid_gen.py  -- generate Mermaid flowchart from block-based schedule
"""


def fmt_time(minutes):
    if minutes >= 60:
        h = minutes / 60
        return ("%.0fh" if h == int(h) else "%.1fh") % h
    return "%gmin" % minutes


def block_to_mermaid_nodes(block, block_idx):
    """Return (subgraph_label, nodes, edges, loop_edge) for one block."""
    btype = block["type"]
    p     = block.get("params", {})
    bid   = "B%d" % block_idx
    nodes = []
    edges = []
    subgraph_label = ""
    loop_edge = None

    if btype == "rest":
        dur = p.get("duration_min", 30)
        rec = p.get("record_time_s", 30)
        subgraph_label = "REST"
        n = "%s_R" % bid
        nodes.append((n, "REST\\n%s  (rec %gs)" % (fmt_time(dur), rec)))

    elif btype == "capacity_check":
        subgraph_label = "Capacity Check"
        n1 = "%s_CC" % bid; n2 = "%s_CR" % bid
        n3 = "%s_CD" % bid; n4 = "%s_DR" % bid
        nodes = [
            (n1, "CCCV Charge\\n%gV @ %.2fC" % (p.get("charge_voltage_V", 4.2), p.get("charge_c_rate", 0.1))),
            (n2, "REST\\n%s" % fmt_time(p.get("rest_after_charge_min", 30))),
            (n3, "CC Discharge\\n%gV cutoff" % p.get("discharge_voltage_V", 2.5)),
            (n4, "REST\\n%s" % fmt_time(p.get("rest_after_discharge_min", 30))),
        ]
        edges = ["%s --> %s" % (nodes[i][0], nodes[i+1][0]) for i in range(len(nodes)-1)]

    elif btype == "soc_setting":
        soc = p.get("target_soc_percent", 50)
        subgraph_label = "SOC Setting -> %d%%" % soc
        n1 = "%s_SC" % bid; n2 = "%s_SR" % bid
        n3 = "%s_SD" % bid; n4 = "%s_StR" % bid
        nodes = [
            (n1, "CCCV Full Charge"),
            (n2, "REST\\n%s" % fmt_time(p.get("rest_min", 30))),
            (n3, "CC Discharge\\nto SOC %d%%" % soc),
            (n4, "REST\\n%s  (stabilize)" % fmt_time(p.get("rest_min", 30))),
        ]
        edges = ["%s --> %s" % (nodes[i][0], nodes[i+1][0]) for i in range(len(nodes)-1)]

    elif btype == "cycle":
        count    = p.get("count", 1)
        ch_mode  = p.get("charge_mode", "cccv")
        ch_label = "CCCV" if ch_mode == "cccv" else "CC"
        subgraph_label = "Cycle  x%d" % count
        n1 = "%s_CC" % bid; n2 = "%s_CR" % bid
        n3 = "%s_CD" % bid; n4 = "%s_DR" % bid
        nodes = [
            (n1, "%s Charge\\n%gV @ %.2fC" % (ch_label, p.get("charge_voltage_V", 4.2), p.get("charge_c_rate", 0.5))),
            (n2, "REST\\n%s" % fmt_time(p.get("rest_after_charge_min", 30))),
            (n3, "CC Discharge\\n%.2fC -> %gV" % (p.get("discharge_c_rate", 0.5), p.get("discharge_voltage_V", 2.5))),
            (n4, "REST\\n%s" % fmt_time(p.get("rest_after_discharge_min", 30))),
        ]
        edges = ["%s --> %s" % (nodes[i][0], nodes[i+1][0]) for i in range(len(nodes)-1)]
        loop_edge = (n4, n1, "x%d" % count)

    elif btype == "rate_test":
        c_rates = p.get("c_rates", [])
        subgraph_label = "Rate Test  (%d C-rates, CC charge)" % len(c_rates)
        prev_end = None
        for gi, group in enumerate(c_rates):
            cr  = group["c_rate"]
            cnt = group.get("count", 1)
            gid = "%s_G%d" % (bid, gi)
            n1  = "%s_CC" % gid; n2 = "%s_CR" % gid
            n3  = "%s_CD" % gid; n4 = "%s_DR" % gid
            nodes += [
                (n1, "CC Charge\\n%.2fC -> %gV" % (cr, p.get("charge_voltage_V", 4.2))),
                (n2, "REST\\n%s" % fmt_time(p.get("rest_after_charge_min", 30))),
                (n3, "CC Discharge\\n%.2fC -> %gV" % (group.get("discharge_c_rate", cr), p.get("discharge_voltage_V", 2.5))),
                (n4, "REST\\n%s" % fmt_time(p.get("rest_after_discharge_min", 30))),
            ]
            edges += ["%s --> %s" % (nodes[-(4-i)][0], nodes[-(3-i)][0]) for i in range(3)]
            if cnt > 1:
                edges.append("%s -->|x%d| %s" % (n4, cnt, n1))
            if prev_end:
                edges.append("%s --> %s" % (prev_end, n1))
            prev_end = n4

    elif btype == "pulse_test":
        soc_mode = p.get("soc_mode", "interval")
        if soc_mode == "interval":
            interval  = p.get("soc_interval_percent", 10)
            soc_label = "SOC every %d%%" % interval
            n_pts     = 100 // interval
        else:
            soc_pts   = sorted(p.get("soc_points", [80, 60, 40, 20]), reverse=True)
            soc_label = "SOC " + ", ".join(str(s) + "%" for s in soc_pts)
            n_pts     = len(soc_pts)

        c_rate   = p.get("pulse_c_rate", 1.5)
        pulse_s  = p.get("pulse_duration_s", 30)
        ret_on   = p.get("return_pulse", True)
        ret_cr   = p.get("return_c_rate", 0.1)
        subgraph_label = "Pulse Test  (%s)" % soc_label

        n_fc = "%s_FC" % bid; n_fr = "%s_FR" % bid
        nodes = [
            (n_fc, "CCCV Full Charge"),
            (n_fr, "REST"),
        ]
        edges = ["%s --> %s" % (n_fc, n_fr)]

        n_sa = "%s_SA" % bid; n_sr = "%s_SR" % bid
        n_ms = "%s_MS" % bid; n_mp = "%s_MP" % bid; n_mr = "%s_MR" % bid
        nodes += [
            (n_sa, "SOC Adjust\\n(DOD %%, cap ref)"),
            (n_sr, "REST"),
            (n_ms, "REST\\n(stabilize %s)" % fmt_time(p.get("stabilization_min", 60))),
            (n_mp, "Pulse di\\n%.2fC  %ds" % (c_rate, pulse_s)),
            (n_mr, "REST\\n(recovery %s)" % fmt_time(p.get("recovery_min", 30))),
        ]
        edges += [
            "%s --> %s" % (n_fr, n_sa),
            "%s --> %s" % (n_sa, n_sr),
            "%s --> %s" % (n_sr, n_ms),
            "%s --> %s" % (n_ms, n_mp),
            "%s --> %s" % (n_mp, n_mr),
        ]

        if ret_on:
            n_rp = "%s_RP" % bid; n_rr = "%s_RR" % bid
            nodes += [
                (n_rp, "Return Charge\\n%.2fC  100%% cap" % ret_cr),
                (n_rr, "REST"),
            ]
            edges += [
                "%s --> %s" % (n_mr, n_rp),
                "%s --> %s" % (n_rp, n_rr),
            ]
            last_m = n_rr
        else:
            last_m = n_mr

        loop_edge = (last_m, n_sa, "x%d SOC pts" % n_pts)

    return subgraph_label, nodes, edges, loop_edge


def schedule_to_mermaid(schedule):
    """Generate Mermaid flowchart code from block-based schedule dict."""
    blocks = schedule.get("blocks", [])
    if not blocks:
        return "flowchart TD\n  START([Empty schedule])"

    lines = ["flowchart TD"]
    all_subgraphs = []

    COLOR_MAP = {
        "rest":           "#e8f4fd",
        "capacity_check": "#fff3cd",
        "soc_setting":    "#d4edda",
        "cycle":          "#f8d7da",
        "rate_test":      "#e2d9f3",
        "pulse_test":     "#d1ecf1",
    }

    for bi, block in enumerate(blocks):
        label, nodes, edges, loop_edge = block_to_mermaid_nodes(block, bi)
        if not nodes:
            continue

        bid = "B%d" % bi
        lines.append('  subgraph %s["%s"]' % (bid, label))

        for nid, nlabel in nodes:
            safe = nlabel.replace('"', "'")
            lines.append('    %s["%s"]' % (nid, safe))

        for e in edges:
            lines.append("    " + e)

        if loop_edge:
            src, dst, lbl = loop_edge
            lines.append('    %s -->|"%s"| %s' % (src, lbl, dst))

        lines.append("  end")

        color = COLOR_MAP.get(block["type"], "#f5f5f5")
        lines.append("  style %s fill:%s,stroke:#333" % (bid, color))
        all_subgraphs.append(bid)

    for i in range(len(all_subgraphs) - 1):
        lines.append("  %s --> %s" % (all_subgraphs[i], all_subgraphs[i+1]))

    if all_subgraphs:
        lines.append('  %s --> END(["END"])' % all_subgraphs[-1])
        lines.append('  style END fill:#343a40,color:#fff,stroke:#343a40')

    return "\n".join(lines)
