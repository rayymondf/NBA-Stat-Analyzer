import { useSearchParams } from "react-router-dom";
import { PageHeader, Segmented } from "../components/ui";
import ModelExplainer from "../components/model/ModelExplainer";
import VsModelMode from "../components/model/VsModelMode";
import HeadToHead from "../components/model/HeadToHead";

type Mode = "vs-model" | "h2h";

export default function ModelLab() {
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get("mode") === "h2h" ? "h2h" : "vs-model";

  const setMode = (m: Mode) => {
    const next = new URLSearchParams(params);
    if (m === "h2h") next.set("mode", "h2h");
    else next.delete("mode");
    setParams(next);
  };

  return (
    <div>
      <PageHeader
        kicker="Machine learning"
        title="The Model"
        dek={
          "Trained on hundreds of thousands of real NBA shots, the model " +
          "learns the odds of a make from any court position, distance and " +
          "situation. Pick a player: the model estimates what an average " +
          "NBA player would shoot on that exact set of shots. The gap " +
          "between that estimate and the player's actual shooting shows " +
          "who outperforms their shot selection and who is cashing in easy " +
          "looks. Switch to Player vs Player for a classic head-to-head."
        }
      />
      <div className="mb-5">
        <Segmented<Mode>
          options={[
            { value: "vs-model", label: "Player vs the Model" },
            { value: "h2h", label: "Player vs Player" },
          ]}
          value={mode}
          onChange={setMode}
        />
      </div>

      {mode === "vs-model" ? <VsModelMode /> : <HeadToHead />}

      <div className="mt-8">
        <ModelExplainer />
      </div>
    </div>
  );
}
