import { useEffect, useRef, useState } from "react";
import {
  forceSimulation,
  forceManyBody,
  forceLink,
  forceCenter,
  forceCollide,
  forceX,
  forceY,
  type SimulationNodeDatum,
} from "d3-force";
import { api, GraphData } from "../api";

type SNode = SimulationNodeDatum & { id: string; label: string; degree: number };
type SLink = { source: string | SNode; target: string | SNode; typed: boolean };

const LOW = [120, 104, 235];
const HIGH = [176, 214, 255];
const mix = (a: number[], b: number[], t: number) =>
  `rgb(${Math.round(a[0] + (b[0] - a[0]) * t)},${Math.round(a[1] + (b[1] - a[1]) * t)},${Math.round(a[2] + (b[2] - a[2]) * t)})`;
const asNode = (v: string | SNode) => v as SNode;

export function Graph({ onOpenNote }: { onOpenNote?: (title: string) => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [g, setG] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const view = useRef({ scale: 1, ox: 0, oy: 0, drag: false, px: 0, py: 0, moved: 0, autofit: true });
  const hover = useRef<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .graph()
      .then((r) => setG(r.data))
      .catch(() => setG({ nodes: [], edges: [] }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !g || g.nodes.length === 0) return;
    const ctx = canvas.getContext("2d")!;

    const maxDeg = Math.max(1, ...g.nodes.map((n) => n.degree));
    const nodes: SNode[] = g.nodes.map((n) => ({ id: n.id, label: n.label, degree: n.degree }));
    const links: SLink[] = g.edges.map((e) => ({ source: e.source, target: e.target, typed: e.typed }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const ratio = (n: SNode) => n.degree / maxDeg;
    const radius = (n: SNode) => 3 + 10 * Math.pow(ratio(n), 0.7);
    const adj = new Map<string, Set<string>>();
    for (const e of g.edges) {
      (adj.get(e.source) ?? adj.set(e.source, new Set()).get(e.source)!).add(e.target);
      (adj.get(e.target) ?? adj.set(e.target, new Set()).get(e.target)!).add(e.source);
    }
    const labelSet = new Set(
      [...nodes].sort((a, b) => b.degree - a.degree).slice(0, 11).map((n) => n.id),
    );

    let W = 0, H = 0, dpr = 1;
    const tx = () => W / 2 + view.current.ox;
    const ty = () => H / 2 + view.current.oy;

    const fit = () => {
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const n of nodes) {
        if (n.x == null || n.y == null) continue;
        minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
        minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
      }
      if (!isFinite(minX)) return;
      const pad = 90;
      const s = Math.min((W - pad) / Math.max(1, maxX - minX), (H - pad) / Math.max(1, maxY - minY), 2.2);
      view.current.scale = Math.max(0.12, Math.min(2.4, s || 1));
    };

    const draw = () => {
      dpr = window.devicePixelRatio || 1;
      W = canvas.clientWidth;
      H = canvas.clientHeight;
      if (canvas.width !== Math.round(W * dpr)) canvas.width = Math.round(W * dpr);
      if (canvas.height !== Math.round(H * dpr)) canvas.height = Math.round(H * dpr);
      if (view.current.autofit) fit();
      const { scale } = view.current;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(tx(), ty());
      ctx.scale(scale, scale);

      const hot = hover.current;
      const near = hot ? (adj.get(hot) ?? new Set<string>()) : null;

      for (const e of links) {
        const a = asNode(e.source), b = asNode(e.target);
        if (a.x == null || b.x == null) continue;
        const lit = hot && (a.id === hot || b.id === hot);
        const faded = hot && !lit;
        ctx.globalAlpha = faded ? 0.22 : 1;
        ctx.strokeStyle = lit
          ? "rgba(79,195,247,0.8)"
          : e.typed
            ? "rgba(135,160,255,0.3)"
            : "rgba(120,104,235,0.12)";
        ctx.lineWidth = (lit ? 1.8 : e.typed ? 1.1 : 0.6) / scale;
        const mx = (a.x! + b.x!) / 2, my = (a.y! + b.y!) / 2;
        const nx = -(b.y! - a.y!), ny = b.x! - a.x!;
        const len = Math.hypot(nx, ny) || 1;
        const k = Math.hypot(b.x! - a.x!, b.y! - a.y!) * 0.06;
        ctx.beginPath();
        ctx.moveTo(a.x!, a.y!);
        ctx.quadraticCurveTo(mx + (nx / len) * k, my + (ny / len) * k, b.x!, b.y!);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      for (const n of nodes) {
        if (n.x == null || n.y == null) continue;
        const t = ratio(n), r = radius(n);
        const isHot = n.id === hot;
        const dim = hot && !isHot && !near?.has(n.id);
        ctx.globalAlpha = dim ? 0.3 : 1;
        if (isHot || t > 0.45) {
          ctx.fillStyle = isHot ? "rgba(79,195,247,0.22)" : "rgba(120,104,235,0.15)";
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

      ctx.textBaseline = "middle";
      for (const n of nodes) {
        if (n.x == null) continue;
        const show = n.id === hot || near?.has(n.id) || (!hot && labelSet.has(n.id));
        if (!show) continue;
        const r = radius(n);
        const fs = (n.id === hot ? 13 : 12) / scale;
        ctx.font = `${n.id === hot ? 600 : 500} ${fs}px ui-sans-serif, system-ui, sans-serif`;
        const tw = ctx.measureText(n.label).width;
        const lx = n.x + r + 6 / scale, ly = n.y!;
        const pad = 4 / scale;
        ctx.fillStyle = "rgba(10,14,20,0.66)";
        ctx.beginPath();
        ctx.roundRect(lx - pad, ly - fs / 2 - pad, tw + pad * 2, fs + pad * 2, 4 / scale);
        ctx.fill();
        ctx.fillStyle = n.id === hot ? "#EAF6FF" : "rgba(213,221,235,0.92)";
        ctx.fillText(n.label, lx, ly + 0.5 / scale);
      }
      ctx.restore();
    };

    const sim = forceSimulation(nodes)
      .force("charge", forceManyBody().strength(-58).distanceMax(380))
      .force("link", forceLink<SNode, SLink>(links).id((d) => d.id).distance(32).strength(0.6))
      .force("collide", forceCollide<SNode>().radius((n) => radius(n) + 3).iterations(2))
      .force("center", forceCenter(0, 0))
      .force("x", forceX(0).strength(0.05))
      .force("y", forceY(0).strength(0.05));
    sim.on("tick", draw);
    sim.on("end", () => {
      view.current.autofit = false;
      draw();
    });

    // Paint immediately even if requestAnimationFrame is throttled (hidden or
    // background tab, low-power mode): d3's tick loop is RAF-driven and would
    // otherwise leave the canvas blank until the tab is focused. Settle the
    // layout synchronously and draw one frame; the RAF ticks still animate it
    // when the page is visible.
    for (let i = 0; i < 90; i++) sim.tick();
    draw();

    const worldAt = (sx: number, sy: number) => ({
      x: (sx - tx()) / view.current.scale,
      y: (sy - ty()) / view.current.scale,
    });
    const hit = (sx: number, sy: number): SNode | null => {
      const w = worldAt(sx, sy);
      let best: SNode | null = null, bestD = Infinity;
      for (const n of nodes) {
        if (n.x == null) continue;
        const d = (w.x - n.x) ** 2 + (w.y - n.y!) ** 2;
        const rr = (radius(n) + 6) ** 2;
        if (d <= rr && d < bestD) { best = n; bestD = d; }
      }
      return best;
    };

    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      view.current.autofit = false;
      view.current.scale = Math.min(4, Math.max(0.1, view.current.scale * (ev.deltaY < 0 ? 1.12 : 0.89)));
      draw();
    };
    const onDown = (ev: MouseEvent) => {
      view.current.autofit = false;
      view.current.drag = true;
      view.current.moved = 0;
      view.current.px = ev.clientX;
      view.current.py = ev.clientY;
    };
    const onMove = (ev: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      if (view.current.drag) {
        view.current.ox += ev.clientX - view.current.px;
        view.current.oy += ev.clientY - view.current.py;
        view.current.moved += Math.abs(ev.clientX - view.current.px) + Math.abs(ev.clientY - view.current.py);
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
      sim.stop();
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
            "radial-gradient(900px 600px at 50% 45%, rgba(110,91,255,0.08), transparent 62%), #0A0E14",
        }}
      >
        <canvas ref={ref} style={{ width: "100%", height: "100%", display: "block", cursor: "grab" }} />
        {loading ? (
          <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "var(--muted)", fontSize: 13 }}>
            Mapping the constellation…
          </div>
        ) : g && g.nodes.length === 0 ? (
          <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "var(--faint)", fontSize: 13 }}>
            No notes yet — import a document to start the constellation.
          </div>
        ) : null}
      </div>
    </div>
  );
}
