/** Plain-English one-liners for every advanced stat shown in the app. */
export const GLOSSARY: Record<string, string> = {
  TS_PCT:
    "True Shooting %: scoring efficiency counting 2s, 3s and free throws together. League average is around 57%.",
  EFG_PCT:
    "Effective FG%: field-goal percentage adjusted so 3-pointers count 1.5x, since they're worth more.",
  USG_PCT:
    "Usage rate: the share of team possessions this player finishes with a shot, free throws or turnover while on the floor.",
  AST_TO: "Assist-to-turnover ratio: assists divided by turnovers. Higher is better.",
  AST_PCT: "Assist %: the share of teammate baskets this player assisted while on the floor.",
  TOV_PCT: "Turnover %: turnovers per 100 plays the player uses. Lower is better.",
  TM_TOV_PCT: "Turnover %: turnovers per 100 plays the player uses. Lower is better.",
  FT_RATE: "Free-throw rate: free-throw attempts per field-goal attempt. Measures how often a player gets to the line.",
  PTS_PER_POSS: "Points per possession used: points scored per scoring attempt or turnover.",
  PTS_PER_SHOT: "Points per shot: points from field goals divided by attempts.",
  OFF_RATING: "Offensive rating: team points scored per 100 possessions while this player is on court.",
  DEF_RATING: "Defensive rating: team points allowed per 100 possessions while on court. Lower is better.",
  NET_RATING: "Net rating: point margin per 100 possessions while on court (offense minus defense).",
  PIE: "Player Impact Estimate: NBA.com's catch-all share of game events a player produces. 10% is average.",
  PACE: "Pace: possessions per 48 minutes while this player is on the floor.",
  PLUS_MINUS: "Plus-minus: team point margin while the player was on the floor.",
  PER_36: "Per-36: stats scaled to 36 minutes of playing time, removing minutes differences.",
  PER_75: "Per-75: stats scaled to 75 team possessions, removing both minutes and pace differences.",
  PER_100: "Per-100: stats scaled to 100 team possessions while on the floor.",
  PERCENTILE:
    "Percentile vs same position. For example, 84th percentile means better than 84% of players at this position (min. 10 games, 15 MPG).",
  ON_OFF:
    "On/off: how the team performs with this player on court vs on the bench. An estimate: lineups and opponents make it noisy in small samples.",
  FG3A_RATE: "3-point attempt rate: the share of field-goal attempts taken from three.",
  XFG:
    "Shot quality (xFG): a machine-learning model trained on real NBA shots estimates what an average NBA player would shoot from this player's exact shot locations and types. Making more than expected means shot-making skill beyond shot selection. A model estimate built from shot locations and types only, never video.",
  POSS: "Possessions: team possessions while the player was on the floor.",
  CLUTCH: "Clutch: the last 5 minutes of a game with the score within 5 points.",
  FOUR_FACTORS:
    "Four factors: shooting (eFG%), turnovers, offensive rebounding and free throws. The four things that decide games.",
};
