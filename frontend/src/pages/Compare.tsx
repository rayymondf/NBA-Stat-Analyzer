import { PageHeader } from "../components/ui";
import HeadToHead from "../components/model/HeadToHead";

export default function Compare() {
  return (
    <div className="min-w-0">
      <PageHeader kicker="Player analysis" title="Compare Players" dek="Two players. One period. Compare production, efficiency and shot selection side by side." />
      <HeadToHead />
    </div>
  );
}
