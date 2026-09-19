import { Navigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/ui";
import ModelExplainer from "../components/model/ModelExplainer";
import VsModelMode from "../components/model/VsModelMode";

export default function ModelLab() {
  const [params] = useSearchParams();
  if (params.get("mode") === "h2h") {
    const next = new URLSearchParams(params);
    next.delete("mode");
    return <Navigate to={`/compare?${next.toString()}`} replace />;
  }

  return (
    <div className="space-y-6 min-w-0">
      <PageHeader kicker="Shot analysis" title="Shot Quality" dek="Compare a player's actual shooting with the model's estimate for the shots they took." />
      <VsModelMode />
      <details className="card p-5">
        <summary className="cursor-pointer font-semibold">Model methodology & evidence</summary>
        <p className="text-sm text-ink-muted mt-2 mb-4">Training data, evaluation, calibration, drift and dataset download.</p>
        <ModelExplainer />
      </details>
    </div>
  );
}
