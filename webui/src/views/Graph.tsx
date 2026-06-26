import { useEffect, useRef, useState } from "react";
import { api, GraphData } from "../api";

export function Graph() {
  const ref = useRef<HTMLCanvasElement>(null);
  const [g, setG] = useState<GraphData | null>(null);
  const view = useRef({ scale: 1, ox: 0, oy: 0, drag: false, px: 0, py: 0 });

  useEffect(() => {
    api
      .graph()
      .then((r) => setG(r.data))
      .catch(() => setG({ nodes: [], edges: [], width: 900, height: 600 }));
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !g) return;
    const ctx = canvas.getContext("2d")!;
    const byId = new Map(g.nodes.map((n) => [n.id, n]));
    const draw = () => {
      const { scale, ox, oy } = view.current;
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      ctx.fillStyle = "#0A0E14";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(ox + canvas.width / 2 - (g.width / 2) * scale, oy + canvas.height / 2 - (g.height / 2) * scale);
      ctx.scale(scale, scale);
      for (const e of g.edges) {
        const a = byId.get(e.source);
        const b = byId.get(e.target);
        if (!a || !b) continue;
        ctx.strokeStyle = e.typed ? "rgba(110,91,255,0.55)" : "rgba(110,91,255,0.25)";
        ctx.lineWidth = e.typed ? 1.4 : 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      for (const n of g.nodes) {
        ctx.beginPath();
        ctx.fillStyle = "rgba(110,91,255,0.18)";
        ctx.arc(n.x, n.y, n.r + 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.fillStyle = n.degree > 2 ? "#B7ADFF" : "#8B7BFF";
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#C9D2E0";
        ctx.font = "11px sans-serif";
        ctx.fillText(n.label, n.x + n.r + 4, n.y + 3);
      }
      ctx.restore();
    };
    draw();
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      view.current.scale = Math.min(3, Math.max(0.3, view.current.scale * (ev.deltaY < 0 ? 1.1 : 0.9)));
      draw();
    };
    const onDown = (ev: MouseEvent) => {
      view.current.drag = true;
      view.current.px = ev.clientX;
      view.current.py = ev.clientY;
    };
    const onMove = (ev: MouseEvent) => {
      if (!view.current.drag) return;
      view.current.ox += ev.clientX - view.current.px;
      view.current.oy += ev.clientY - view.current.py;
      view.current.px = ev.clientX;
      view.current.py = ev.clientY;
      draw();
    };
    const onUp = () => {
      view.current.drag = false;
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("resize", draw);
    return () => {
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("resize", draw);
    };
  }, [g]);

  return (
    <div style={{ height: "100%" }}>
      <h2 style={{ marginTop: 0 }}>Graph</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, marginBottom: 10 }}>
        the most connected notes — drag to pan, wheel to zoom
      </div>
      <canvas
        ref={ref}
        style={{
          width: "100%",
          height: "calc(100% - 64px)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          cursor: "grab",
          display: "block",
        }}
      />
    </div>
  );
}
