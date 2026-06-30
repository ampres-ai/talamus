import { useEffect, useRef, useState } from "react";
import { api, GraphData, GraphNode } from "../api";

// linear blend between two hex colors (0..1)
function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bl = Math.round(a[2] + (b[2] - a[2]) * t);
  return `rgb(${r},${g},${bl})`;
}
const LOW: [number, number, number] = [110, 91, 255]; // indigo
const HIGH: [number, number, number] = [150, 200, 255]; // toward cyan-white

export function Graph({ onOpenNote }: { onOpenNote?: (title: string) => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [g, setG] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const view = useRef({ scale: 1, ox: 0, oy: 0, drag: false, px: 0, py: 0, moved: 0, fitted: false });
  const hover = useRef<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .graph()
      .then((r) => setG(r.data))
      .catch(() => setG({ nodes: [], edges: [], width: 900, height: 600 }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !g || g.nodes.length === 0) return;
    const ctx = canvas.getContext("2d")!;
    const byId = new Map(g.nodes.map((n) => [n.id, n]));
    const maxDeg = Math.max(1, ...g.nodes.map((n) => n.degree));

    const xs = g.nodes.map((n) => n.x);
    const ys = g.nodes.map((n) => n.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

    const adj = new Map<string, Set<string>>();
    for (const e of g.edges) {
      (adj.get(e.source) ?? adj.set(e.source, new Set()).get(e.source)!).add(e.target);
      (adj.get(e.target) ?? adj.set(e.target, new Set()).get(e.target)!).add(e.source);
    }

    let W = 0, H = 0, dpr = 1;
    const sizeToBox = () => {
      dpr = window.devicePixelRatio || 1;
      W = canvas.clientWidth;
      H = canvas.clientHeight;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    };
    const tx = () => W / 2 - cx * view.current.scale + view.current.ox;
    const ty = () => H / 2 - cy * view.current.scale + view.current.oy;

    const fit = () => {
      const pad = 80;
      const bw = Math.max(1, maxX - minX), bh = Math.max(1, maxY - minY);
      const s = Math.min((W - pad) / bw, (H - pad) / bh, 1.6);
      view.current.scale = Math.max(0.3, Math.min(2.4, s || 1));
      view.current.ox = 0;
      view.current.oy = 0;
      view.current.fitted = true;
    };

    const draw = () => {
      sizeToBox();
      if (!view.current.fitted) fit();
      const { scale } = view.current;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(tx(), ty());
      ctx.scale(scale, scale);

      const hot = hover.current;
      const near = hot ? adj.get(hot) ?? new Set<string>() : null;

      // edges
      for (const e of g.edges) {
        const a = byId.get(e.source);
        const b = byId.get(e.target);
        if (!a || !b) continue;
        const lit = hot && (e.source === hot || e.target === hot);
        if (lit) ctx.strokeStyle = "rgba(79,195,247,0.7)";
        else if (e.typed) ctx.strokeStyle = "rgba(125,150,255,0.34)";
        else ctx.strokeStyle = hot ? "rgba(110,91,255,0.07)" : "rgba(110,91,255,0.16)";
        ctx.lineWidth = (lit ? 1.8 : e.typed ? 1.2 : 0.8) / scale;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }

      // nodes
      for (const n of g.nodes) {
        const t = n.degree / maxDeg;
        const dim = hot && n.id !== hot && !near?.has(n.id);
        const core = mix(LOW, HIGH, t);
        // soft Aurora halo
        ctx.fillStyle = `rgba(110,91,255,${dim ? 0.04 : 0.1})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r + 9, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = `rgba(110,91,255,${dim ? 0.08 : 0.2})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r + 4, 0, Math.PI * 2);
        ctx.fill();
        // core
        ctx.globalAlpha = dim ? 0.45 : 1;
        ctx.fillStyle = n.id === hot ? "#BFE6FF" : core;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.lineWidth = 1 / scale;
        ctx.strokeStyle = "rgba(255,255,255,0.2)";
        ctx.stroke();
        ctx.globalAlpha = 1;
        // label — only where it won't clutter (important nodes, hovered, or zoomed in)
        const show = n.id === hot || (!dim && (t > 0.34 || scale > 1.1));
        if (show) {
          ctx.fillStyle = n.id === hot ? "#EAF6FF" : "rgba(201,210,224,0.85)";
          ctx.font = `${n.id === hot ? 600 : 400} ${12 / scale}px ui-sans-serif, system-ui, sans-serif`;
          ctx.fillText(n.label, n.x + n.r + 5 / scale, n.y + 4 / scale);
        }
      }
      ctx.restore();
    };

    const worldAt = (sx: number, sy: number) => ({
      x: (sx - tx()) / view.current.scale,
      y: (sy - ty()) / view.current.scale,
    });
    const hit = (sx: number, sy: number): GraphNode | null => {
      const w = worldAt(sx, sy);
      let best: GraphNode | null = null;
      let bestD = Infinity;
      for (const n of g.nodes) {
        const dx = w.x - n.x, dy = w.y - n.y;
        const d = dx * dx + dy * dy;
        const rr = (n.r + 7) * (n.r + 7);
        if (d <= rr && d < bestD) {
          best = n;
          bestD = d;
        }
      }
      return best;
    };

    draw();
    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);

    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      view.current.scale = Math.min(3.5, Math.max(0.2, view.current.scale * (ev.deltaY < 0 ? 1.12 : 0.89)));
      draw();
    };
    const onDown = (ev: MouseEvent) => {
      view.current.drag = true;
      view.current.moved = 0;
      view.current.px = ev.clientX;
      view.current.py = ev.clientY;
    };
    const onMove = (ev: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      if (view.current.drag) {
        const dx = ev.clientX - view.current.px;
        const dy = ev.clientY - view.current.py;
        view.current.moved += Math.abs(dx) + Math.abs(dy);
        view.current.ox += dx;
        view.current.oy += dy;
        view.current.px = ev.clientX;
        view.current.py = ev.clientY;
        draw();
        return;
      }
      const h = hit(ev.clientX - rect.left, ev.clientY - rect.top);
      const id = h?.id ?? null;
      if (id !== hover.current) {
        hover.current = id;
        canvas.style.cursor = id ? "pointer" : "grab";
        draw();
      }
    };
    const onUp = (ev: MouseEvent) => {
      const wasClick = view.current.drag && view.current.moved < 5;
      view.current.drag = false;
      if (wasClick && onOpenNote) {
        const rect = canvas.getBoundingClientRect();
        const node = hit(ev.clientX - rect.left, ev.clientY - rect.top);
        if (node) onOpenNote(node.id);
      }
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      ro.disconnect();
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [g, onOpenNote]);

  const capped = g && g.total != null && g.shown != null && g.total > g.shown;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h2 style={{ margin: 0 }}>Graph</h2>
        {g ? (
          <span style={{ color: "var(--muted)", fontSize: 13 }} className="tnum">
            {capped ? `top ${g.shown} of ${g.total} notes` : `${g.nodes.length} notes`}
          </span>
        ) : null}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 12px" }}>
        The living constellation — drag to pan, wheel to zoom, hover to trace links, click a node
        to open it.
      </div>
      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 0,
          border: "1px solid var(--border)",
          borderRadius: "var(--r-lg)",
          overflow: "hidden",
          background:
            "radial-gradient(900px 520px at 50% 18%, rgba(110,91,255,0.08), transparent 60%), #0A0E14",
        }}
      >
        <canvas
          ref={ref}
          style={{ width: "100%", height: "100%", display: "block", cursor: "grab" }}
        />
        {loading ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              color: "var(--muted)",
              fontSize: 13,
            }}
          >
            Mapping the constellation…
          </div>
        ) : g && g.nodes.length === 0 ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              color: "var(--faint)",
              fontSize: 13,
              textAlign: "center",
            }}
          >
            No notes yet — import a document to start the constellation.
          </div>
        ) : null}
      </div>
    </div>
  );
}
