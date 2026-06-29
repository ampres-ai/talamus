import "./theme.css";
import { useState } from "react";
import { Shell } from "./shell/Shell";
import { Inspector } from "./shell/Inspector";
import { Home } from "./views/Home";
import { Ask } from "./views/Ask";
import { Graph } from "./views/Graph";
import { Library } from "./views/Library";
import { Ontology } from "./views/Ontology";
import { Review } from "./views/Review";
import { System } from "./views/System";

export default function App() {
  const [note, setNote] = useState<string | null>(null);
  return (
    <Shell
      views={{
        home: <Home />,
        ask: <Ask onOpenNote={setNote} />,
        graph: <Graph onOpenNote={setNote} />,
        library: <Library />,
        ontology: <Ontology />,
        review: <Review onOpenNote={setNote} />,
        system: <System />,
      }}
      inspector={note ? <Inspector title={note} onClose={() => setNote(null)} /> : null}
    />
  );
}
