export type YafaAnswerMap = Record<string, string>;
export type YafaStepType = "single_select" | "binary" | "image_upload" | "results";

export type YafaStep = {
  id: string;
  question: string;
  type: YafaStepType;
  options?: Array<{ label: string; value: string }>;
  condition?: (answers: YafaAnswerMap) => boolean;
};

export const yafaSteps: YafaStep[] = [
  {
    id: "primary_concern",
    question: "What would you like your beauty edit to focus on?",
    type: "single_select",
    options: [
      { label: "Hydration", value: "hydration" }, { label: "Uneven tone", value: "uneven_tone" },
      { label: "Fine lines", value: "fine_lines" }, { label: "Acne-prone", value: "acne_prone" },
      { label: "Sensitivity", value: "sensitivity" }, { label: "Hyperpigmentation", value: "hyperpigmentation" },
    ],
  },
  { id: "skin_feel", question: "How does your skin usually feel through the day?", type: "single_select", options: [{ label: "Tight or dry", value: "tight_dry" }, { label: "Balanced", value: "balanced" }, { label: "Oily by midday", value: "oily_midday" }, { label: "Combination", value: "combination" }] },
  { id: "spf_daily", question: "Do you use SPF daily?", type: "binary", options: [{ label: "Yes", value: "yes" }, { label: "No", value: "no" }] },
  { id: "foundation_finish", question: "Which foundation finish feels most like you?", type: "single_select", options: [{ label: "Matte", value: "matte" }, { label: "Satin", value: "satin" }, { label: "Dewy", value: "dewy" }, { label: "Buildable", value: "buildable" }] },
  { id: "visible_dark_spots", question: "Do you notice visible dark spots or melasma?", type: "single_select", options: [{ label: "Yes", value: "yes" }, { label: "Some", value: "some" }, { label: "No", value: "no" }], condition: (answers) => ["hyperpigmentation", "uneven_tone"].includes(answers.primary_concern) },
  { id: "oil_free", question: "Would you prefer oil-free formulas?", type: "single_select", options: [{ label: "Yes", value: "yes" }, { label: "No", value: "no" }, { label: "Not sure", value: "unsure" }], condition: (answers) => answers.primary_concern === "acne_prone" },
  { id: "routine_time", question: "How much time do you have for your morning routine?", type: "single_select", options: [{ label: "Under 5 minutes", value: "under_5" }, { label: "5–15 minutes", value: "5_15" }, { label: "15–30 minutes", value: "15_30" }, { label: "30+ minutes", value: "over_30" }] },
  { id: "selfie", question: "Would you like to add a selfie for a more personal shade edit?", type: "image_upload" },
  { id: "results", question: "Your Yafa edit", type: "results" },
];

export function visibleYafaSteps(answers: YafaAnswerMap) {
  return yafaSteps.filter((step) => !step.condition || step.condition(answers));
}
