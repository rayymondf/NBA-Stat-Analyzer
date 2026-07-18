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
          "The Model is a machine-learning program that studied hundreds of " +
          "thousands of real NBA shots and learned how often shots go in from " +
          "every spot on the court. When you pick a player, the model plays " +
          "the part of an average NBA player taking that player's exact " +
          "shots, one by one, and predicts what an average player would " +
          "shoot from them. Comparing that prediction with what your player " +
          "actually shot shows whether they make more or less than their " +
          "shots deserve: real shot-making skill, separated from easy or " +
          "hard shot selection. You can also switch to a classic player vs " +
          "player comparison."
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
