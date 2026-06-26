import "./theme.css";
import { Shell } from "./shell/Shell";
import { Home } from "./views/Home";
import { Graph } from "./views/Graph";
import { Library } from "./views/Library";

export default function App() {
  return <Shell views={{ home: <Home />, graph: <Graph />, library: <Library /> }} />;
}
