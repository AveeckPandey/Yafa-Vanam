import YafaWizard from "./YafaWizard";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Yafa Beauty Advisor",
  description: "Build a personal YAFA VANAM beauty profile and discover products selected for your preferences.",
  alternates: { canonical: "/yafa" },
};

export default function YafaPage() {
  return <YafaWizard />;
}
