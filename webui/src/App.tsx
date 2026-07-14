import "./theme.css";
import { useEffect, useState } from "react";
import { api, ActiveBrain } from "./api";
import { Shell } from "./shell/Shell";
import { Inspector } from "./shell/Inspector";
import { Home } from "./views/Home";
import { Ask } from "./views/Ask";
import { Graph } from "./views/Graph";
import { Library } from "./views/Library";
import { Import } from "./views/Import";
import { Ontology } from "./views/Ontology";
import { Review } from "./views/Review";
import { Brains } from "./views/Brains";
import { Connect } from "./views/Connect";
import { System } from "./views/System";

type SwitchOutcome = { success: boolean; message?: string };

export default function App() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    const onOpenNote = (event: Event) => {
      const title = (event as CustomEvent<{ title?: string }>).detail?.title;
      if (typeof title === "string" && title) setNote(title);
    };
    window.addEventListener("talamus:openNote", onOpenNote);
    return () => window.removeEventListener("talamus:openNote", onOpenNote);
  }, []);
  const [active, setActive] = useState<ActiveBrain | null>(null);
  const [version, setVersion] = useState(0); // bumping remounts the shell → views re-fetch

  useEffect(() => {
    api
      .getActive()
      .then((r) => setActive(r.data))
      .catch(() => setActive(null));
  }, []);

  // Re-point every view at the (already-switched) brain without a hard page reload.
  const refresh = async () => {
    try {
      const r = await api.getActive();
      setActive(r.data);
    } catch {
      /* keep the previous active brain */
    }
    setNote(null);
    setVersion((v) => v + 1);
  };

  const switchBrain = async (body: { name?: string; path?: string }): Promise<SwitchOutcome> => {
    const r = await api.setActiveBrain(body);
    if (r.success) await refresh();
    return r;
  };

  const initBrain = async (body: { path: string; name?: string }): Promise<SwitchOutcome> => {
    const r = await api.initBrain(body);
    if (r.success) await refresh();
    return r;
  };

  return (
    <Shell
      key={version}
      activeBrain={active}
      views={{
        home: <Home />,
        ask: <Ask onOpenNote={setNote} />,
        graph: <Graph onOpenNote={setNote} />,
        library: <Library onOpenNote={setNote} />,
        import: <Import />,
        ontology: <Ontology />,
        review: <Review onOpenNote={setNote} />,
        brains: <Brains active={active} onSwitch={switchBrain} onInit={initBrain} />,
        connect: <Connect />,
        system: <System />,
      }}
      inspector={note ? <Inspector title={note} onClose={() => setNote(null)} /> : null}
    />
  );
}
