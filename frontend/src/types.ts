export type Stats = {
  rules_done: number;
  rules_total: number;
  bugs_open: number;
  bugs_active: number;
  ui_reviewed: number;
  ui_total: number;
};

export type IndexFeature = {
  ref: string;
  module: string;
  feature: string;
  name: string;
  stats: Stats;
  parse_ok: boolean;
};

export type IndexPayload = {
  modules: { name: string; features: IndexFeature[] }[];
};

export type FigmaNode = { name: string; file: string; node: string };
export type Rule = {
  id: string;
  status: string;
  context: string | null;
  text: string;
  figma_nodes: FigmaNode[];
};
export type UiReview = {
  status: string;
  date: string;
  findings: { rule: string; text: string }[];
};
export type Requirement = {
  id: string;
  name: string;
  description: string;
  rules: Rule[];
  ui_reviews: UiReview[];
};
export type Bug = {
  id: string;
  status: string;
  date: string;
  rule: string;
  current: string;
  expected: string;
  steps: string;
};
export type Implementation = { platform: string; spec: string };
export type Feature = {
  ref: string;
  module: string;
  feature: string;
  name: string;
  overview: string;
  implementations: Implementation[];
  requirements: Requirement[];
  bugs: Bug[];
  stats: Stats;
  parse_error?: string;
};
