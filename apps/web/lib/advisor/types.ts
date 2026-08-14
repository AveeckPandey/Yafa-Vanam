export type QuizOption = { value: string; label: string; helper?: string | null };
export type QuizStep = { id: string; prompt: string; options: QuizOption[]; skippable?: boolean };
export type Shade = { code?: string | null; name?: string | null; hex?: string | null };
export type Recommendation = {
  category: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  variant_id?: string | null;
  shade?: Shade | null;
  score: number;
  reason_codes: string[];
  image?: string | null;
  commerce_validation_required: boolean;
};
export type AdvisorSession = {
  id: string;
  profile: Record<string, any>;
  answers: Record<string, any>;
  current_step?: QuizStep | null;
  recommendations: Recommendation[];
};
