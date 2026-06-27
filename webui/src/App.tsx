import "./theme.css";
import { useState } from "react";
import { Shell } from "./shell/Shell";
import { Inspector } from "./shell/Inspector";
import { Home } from "./views/Home";
import { Graph } from "./views/Graph";
import { Library } from "./views/Library";
import { Review } from "./views/Review";

export default function App() {
  const [note, setNote] = useState<string | null>(null);
  return (
    <Shell
      views={{
        home: <Home />,
        graph: <Graph onOpenNote={setNote} />,
        library: <Library />,
        review: <Review onOpenNote={setNote} />,
      }}
      inspector={note ? <Inspector title={note} onClose={() => setNote(null)} /> : null}
    />
  );
}
