import { useEffect, useRef, useState } from "react";
import { api, GraphData, GraphNode } from "../api";

const LOW: [number, number, number] = [120, 104, 235]; // indigo (leaves)
const HIGH: [number, number, number] = [176, 214, 255]; // bright (hubs)
const mix = (a: number[], b: number[], t: number) =>
  `rgb(${Math.round(a[0] + (b[0] - a[0]) * t)},${Math.round(a[1] + (b[1] - a[1]) * t)},${Math.round(a[2] + (b[2] - a[2]) * t)})`;
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

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

    const maxDeg = Math.max(1, ...g.nodes.map((n) => n.degree));
    // derived radius for a stronger hub/leaf hierarchy
    const radius = new Map<string, number>();
    const ratio = new Map<string, number>();
    const order = new Map<string, number>(); // entrance stagger order (hubs first)
    [...g.nodes]
      .sort((a, b) => b.degree - a.degree)
      .forEach((n, i) => order.set(n.id, i));
    for (const n of g.nodes) {
      const r = n.degree / maxDeg;
      ratio.set(n.id, r);
      radius.set(n.id, 3 + 10 * Math.pow(r, 0.7));
    }
    const labelSet = new Set(
      [...g.nodes].sort((a, b) => b.degree - a.degree).slice(0, 11).map((n) => n.id),
    );
    const byId = new Map(g.nodes.map((n) => [n.id, n]));
    const adj = new Map<string, Set<string>>();
    for (const e of g.edges) {
      (adj.get(e.source) ?? adj.set(e.source, new Set()).get(e.source)!).add(e.target);
      (adj.get(e.target) ?? adj.set(e.target, new Set()).get(e.target)!).add(e.source);
    }

    const xs = g.nodes.map((n) => n.x);
    const ys = g.nodes.map((n) => n.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

    let W = 0, H = 0, dpr = 1;
    const tx = () => W / 2 - cx * view.current.scale + view.current.ox;
    const ty = () => H / 2 - cy * view.current.scale + view.current.oy;
    const fit = () => {
      const pad = 110;
      const s = Math.min((W - pad) / Math.max(1, maxX - minX), (H - pad) / Math.max(1, maxY - minY), 1.5);
      view.current.scale = Math.max(0.25, Math.min(2, s || 1));
      view.current.ox = 0;
      view.current.oy = 0;
      view.current.fitted = true;
    };

    let start = 0;
    let raf = 0;

    const draw = (now?: number) => {
      dpr = window.devicePixelRatio || 1;
      W = canvas.clientWidth;
      H = canvas.clientHeight;
      if (canvas.width !== Math.round(W * dpr)) canvas.width = Math.round(W * dpr);
      if (canvas.height !== Math.round(H * dpr)) canvas.height = Math.round(H * dpr);
      if (!view.current.fitted) fit();

      const elapsed = now && start ? now - start : 9999;
      const intro = (id: string) => {
        const delay = (order.get(id) ?? 0) * 5;
        return easeOut(Math.max(0, Math.min(1, (elapsed - delay) / 420)));
      };

      const { scale } = view.current;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(tx(), ty());
      ctx.scale(scale, scale);

      const hot = hover.current;
      const near = hot ? (adj.get(hot) ?? new Set<string>()) : null;

      // edges — faint, slightly curved threads (not a spiderweb)
      for (const e of g.edges) {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) continue;
        const p = Math.min(intro(e.source), intro(e.target));
        if (p <= 0.01) continue;
        const lit = hot && (e.source === hot || e.target === hot);
        const faded = hot && !lit;
        ctx.globalAlpha = p * (faded ? 0.25 : 1);
        ctx.strokeStyle = lit
          ? "rgba(79,195,247,0.75)"
          : e.typed
            ? "rgba(135,160,255,0.3)"
            : "rgba(120,104,235,0.13)";
        ctx.lineWidth = (lit ? 1.8 : e.typed ? 1.1 : 0.7) / scale;
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        const nx = -(b.y - a.y), ny = b.x - a.x;
        const len = Math.hypot(nx, ny) || 1;
        const k = Math.hypot(b.x - a.x, b.y - a.y) * 0.07;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.quadraticCurveTo(mx + (nx / len) * k, my + (ny / len) * k, b.x, b.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // nodes
      for (const n of g.nodes) {
        const t = ratio.get(n.id)!;
        const r = radius.get(n.id)! * (0.3 + 0.7 * intro(n.id));
        const isHot = n.id === hot;
        const dim = hot && !isHot && !near?.has(n.id);
        ctx.globalAlpha = intro(n.id) * (dim ? 0.32 : 1);
        // subtle glow only on hubs / hovered (no blanket neon)
        if (isHot || t > 0.45) {
          ctx.fillStyle = isHot ? "rgba(79,195,247,0.22)" : "rgba(120,104,235,0.16)";
          ctx.beginPath();
          ctx.arc(n.x, n.y, r + (isHot ? 10 : 6), 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = isHot ? "#CDEBFF" : mix(LOW, HIGH, t);
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.lineWidth = 1 / scale;
        ctx.strokeStyle = "rgba(255,255,255,0.22)";
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // labels — only hubs + hovered (+ its neighbours), with a legibility backing
      ctx.textBaseline = "middle";
      for (const n of g.nodes) {
        const show = n.id === hot || near?.has(n.id) || (!hot && labelSet.has(n.id));
        if (!show || intro(n.id) < 0.6) continue;
        const r = radius.get(n.id)!;
        const fs = (n.id === hot ? 13 : 12) / scale;
        ctx.font = `${n.id === hot ? 600 : 500} ${fs}px ui-sans-serif, system-ui, sans-serif`;
        const tw = ctx.measureText(n.label).width;
        const lx = n.x + r + 6 / scale, ly = n.y;
        ctx.fillStyle = "rgba(10,14,20,0.66)";
        ctx.beginPath();
        const pad = 4 / scale;
        ctx.roundRect(lx - pad, ly - fs / 2 - pad, tw + pad * 2, fs + pad * 2, 4 / scale);
        ctx.fill();
        ctx.fillStyle = n.id === hot ? "#EAF6FF" : "rgba(213,221,235,0.92)";
        ctx.fillText(n.label, lx, ly + 0.5 / scale);
      }
      ctx.restore();

      if (elapsed < 9999 && elapsed < (g.nodes.length * 5 + 480)) {
        raf = requestAnimationFrame(draw);
      }
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
        const rr = (radius.get(n.id)! + 6) ** 2;
        const d = (w.x - n.x) ** 2 + (w.y - n.y) ** 2;
        if (d <= rr && d < bestD) {
          best = n;
          bestD = d;
        }
      }
      return best;
    };

    start = performance.now();
    draw(start);
    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);

    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      view.current.scale = Math.min(3.5, Math.max(0.18, view.current.scale * (ev.deltaY < 0 ? 1.12 : 0.89)));
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
        const dx = ev.clientX - view.current.px, dy = ev.clientY - view.current.py;
        view.current.moved += Math.abs(dx) + Math.abs(dy);
        view.current.ox += dx;
        view.current.oy += dy;
        view.current.px = ev.clientX;
        view.current.py = ev.clientY;
        draw();
        return;
      }
      const id = hit(ev.clientX - rect.left, ev.clientY - rect.top)?.id ?? null;
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
      cancelAnimationFrame(raf);
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
            {capped ? `${g.shown} most-connected of ${g.total} notes` : `${g.nodes.length} notes`}
          </span>
        ) : null}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 12px" }}>
        Hubs are larger and brighter — hover a note to trace its links, click to open it.
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
            "radial-gradient(820px 520px at 50% 30%, rgba(110,91,255,0.07), transparent 60%), #0A0E14",
        }}
      >
        <canvas ref={ref} style={{ width: "100%", height: "100%", display: "block", cursor: "grab" }} />
        {loading ? (
          <div
            style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "var(--muted)", fontSize: 13 }}
          >
            Mapping the constellation…
          </div>
        ) : g && g.nodes.length === 0 ? (
          <div
            style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "var(--faint)", fontSize: 13 }}
          >
            No notes yet — import a document to start the constellation.
          </div>
        ) : null}
      </div>
    </div>
  );
}
